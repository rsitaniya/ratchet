#!/usr/bin/env python3
"""Reject a patch that touches protected paths (deterministic Gate-4.1 check).

The dev-loop orchestrator runs this before `git apply`. It reads the protected
globs from the active flywheel.toml (`[protected].paths`) and exits non-zero if
the patch touches any protected file. Protected paths are held-out evaluators,
gold labels, fixtures, engines, and scoring — the things the loop must never edit
to make its own metrics pass.

The touched paths come from `git apply --numstat -z`, so Git does its own
unquoting/unescaping — no hand-rolled path decoder is needed on this side. A
patch that renames or copies a file is rejected outright, before any path is even
checked: the implementer has no legitimate reason to rearrange existing files
(new behavior means editing or adding a file), and numstat reports only a
rename's *destination*, never its *source* — accepting renames would require a
second, text-based detector for the source path, which is exactly the kind of
hand-rolled parser this repo's CLAUDE.md warns against trusting for a security
decision. A patch that creates, deletes, or repoints a symlink (file mode
120000) is rejected outright for the same reason — a symlink can point anywhere
on disk, so path-based globs alone cannot bound what a follow-up write through
it can reach.

The guard also refuses to run at all if no flywheel.toml resolves — a missing
config is not the same thing as a config that declares nothing protected, and
blessing a patch because no one configured protection would be the same failure
mode as a bypassed check.

Exit 0 = clean (apply is allowed). Exit 2 = a protected path was touched, a
rename/copy/symlink was attempted, no config resolved, the patch could not be
parsed, or usage was wrong.

Usage:
    python scripts/check_protected_paths.py <patchfile>
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

from flywheel_config import config_path, get_value


class PatchParseError(Exception):
    """Git could not report the paths a patch touches."""


def paths_touched(patchfile: Path) -> list[str]:
    """Paths per `git apply --numstat -z` — the sole source of truth.

    Git emits raw NUL-terminated paths, so it handles quoting/escaping that a
    text parser would get wrong. This does not touch the working tree — numstat
    only parses the patch. Rename and copy patches are rejected before this is
    ever called (see `has_rename_or_copy`), so every record here is an ordinary
    add, modify, or delete.
    """
    proc = subprocess.run(
        ["git", "apply", "--numstat", "-z", str(patchfile)],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise PatchParseError(proc.stderr.decode("utf-8", "replace").strip())
    return _parse_numstat_z(proc.stdout)


def _parse_numstat_z(blob: bytes) -> list[str]:
    """Parse `git apply --numstat -z` output: `<added>\\t<removed>\\t<path>\\0` records."""
    paths: set[str] = set()
    for token in blob.split(b"\0"):
        if not token:
            continue
        parts = token.split(b"\t", 2)
        if len(parts) == 3:
            paths.add(parts[2].decode("utf-8", "surrogateescape"))
    return sorted(paths)


_RENAME_COPY_PREFIXES = ("rename from ", "rename to ", "copy from ", "copy to ", "similarity index ")


def has_rename_or_copy(diff_text: str) -> bool:
    """True if the diff renames or copies a file (see module docstring for why)."""
    for line in diff_text.splitlines():
        if line.lstrip().startswith(_RENAME_COPY_PREFIXES):
            return True
    return False


_SYMLINK_MODE_PREFIXES = ("new file mode ", "old mode ", "new mode ", "deleted file mode ")


def has_symlink_mode_change(diff_text: str) -> bool:
    """True if the diff creates, deletes, or repoints a symlink (file mode 120000).

    A symlink can point anywhere on disk, so a patch that creates one — then a
    later patch that writes through it — can reach a path the protected-path
    globs never see (verified: a symlink into fixtures/, then a write to
    shim/gold_fused.jsonl through it, passes the glob check; only git's own
    refusal to write beyond a symlink stops it). The implementer has no
    legitimate reason to create or modify a symlink, so any 120000 mode is
    rejected outright, independent of which path it's on.
    """
    for line in diff_text.splitlines():
        line = line.rstrip()
        if line.startswith(_SYMLINK_MODE_PREFIXES) and line.endswith("120000"):
            return True
        if line.startswith("index ") and line.endswith(" 120000"):
            return True
    return False


def _matches(path: str, glob: str) -> bool:
    # Match the full path, the path with a leading "**/" stripped (so a
    # repo-root file matches too), and the basename — so `**/evaluate.py`
    # catches evaluate.py wherever it sits and however the diff is prefixed.
    bare = glob[3:] if glob.startswith("**/") else glob
    name = path.rsplit("/", 1)[-1]
    return fnmatch.fnmatch(path, glob) or fnmatch.fnmatch(path, bare) or fnmatch.fnmatch(name, bare)


def protected_hits(paths: list[str], globs: list[str]) -> list[tuple[str, str]]:
    """Return (path, glob) pairs for every changed path that matches a protected glob."""
    hits = []
    for path in paths:
        for glob in globs:
            if _matches(path, glob):
                hits.append((path, glob))
                break
    return hits


def _resolve_config_or_reject() -> Path | None:
    """Resolve the active config, or print a REJECTED message and return None.

    Stricter than flywheel_config.load_config()'s own permissiveness: a missing
    config there is a supported "no app selected" mode for tools like the
    simulator. The guard's job is different — it must never bless a patch
    because no one is enforcing anything, so it insists a real config file
    resolved, whether that would come from $FLYWHEEL_CONFIG or the repo-root
    default.
    """
    try:
        cfg = config_path()
    except FileNotFoundError as e:
        print(f"REJECTED: {e}", file=sys.stderr)
        return None
    if not cfg.exists():
        print(f"REJECTED: no flywheel.toml resolved (looked for {cfg}).", file=sys.stderr)
        print("  Set FLYWHEEL_CONFIG to the active engagement's config so the", file=sys.stderr)
        print("  protected-path list can be resolved. An empty [protected].paths is a", file=sys.stderr)
        print("  valid, explicit choice; a missing config is not the same thing.", file=sys.stderr)
        return None
    return cfg


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: check_protected_paths.py <patchfile>", file=sys.stderr)
        return 2
    if _resolve_config_or_reject() is None:
        return 2
    globs = get_value("protected.paths") or []
    if not globs:
        return 0  # app declares nothing protected
    patchfile = Path(argv[0])
    diff_text = patchfile.read_text(errors="replace")
    if has_rename_or_copy(diff_text):
        print("REJECTED: patch renames or copies a file.", file=sys.stderr)
        print("  The implementer has no legitimate reason to rename or copy a file —", file=sys.stderr)
        print("  make focused edits to the target file instead.", file=sys.stderr)
        return 2
    if has_symlink_mode_change(diff_text):
        print("REJECTED: patch creates, deletes, or repoints a symlink (file mode 120000).", file=sys.stderr)
        print("  A symlink can point anywhere on disk, bypassing path-based protection.", file=sys.stderr)
        return 2
    try:
        paths = paths_touched(patchfile)
    except PatchParseError as e:
        print("REJECTED: git could not determine the patch's targets, so it cannot be", file=sys.stderr)
        print(f"  proven safe: {e}", file=sys.stderr)
        return 2  # fail closed — an unparseable patch is not a clean patch
    hits = protected_hits(paths, globs)
    if hits:
        print("REJECTED: patch touches protected paths (evaluator/gold/fixtures/engines/scoring):", file=sys.stderr)
        for path, glob in hits:
            print(f"  {path}  (matches {glob})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
