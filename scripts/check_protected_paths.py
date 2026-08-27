#!/usr/bin/env python3
"""Reject a set of edits that touches protected paths (deterministic Gate-4.1 check).

The dev-loop orchestrator runs this before applying the implementer's edits. It
reads the protected globs from the active flywheel.toml (`[protected].paths`)
and exits non-zero if any edit's `file` matches. Protected paths are held-out
evaluators, gold labels, fixtures, prior receipts, engines, and scoring — the
things the loop must never edit to make its own metrics pass.

The implementer's output is a JSON list of `{"file", "old_string", "new_string"}`
edits (see apply_edits.py), not a unified diff — so path detection is exact-match
on a field the implementer wrote itself, not a text parse of anything. This also
removes an entire attack class outright: a rename, a copy, and a symlink are all
diff-format operations with no equivalent in the edit contract, so there is
nothing to detect for any of them — the implementer simply cannot express "move
this protected file somewhere the globs don't cover" or "write through a
symlink into a protected directory" in this format at all.

The guard also refuses to run at all if no flywheel.toml resolves — a missing
config is not the same thing as a config that declares nothing protected, and
blessing a submission because no one configured protection would be the same
failure mode as a bypassed check.

Exit 0 = clean (apply is allowed). Exit 2 = a protected path was touched, no
config resolved, the edits file could not be parsed, or usage was wrong.

Usage:
    python scripts/check_protected_paths.py <editsfile.json>
"""
from __future__ import annotations

import fnmatch
import json
import sys
from pathlib import Path

from flywheel_config import config_path, get_value


def touched_paths(edits: list[dict], repo_root: Path) -> list[str]:
    """Repo-relative paths named by `file` across every edit in the batch."""
    paths: set[str] = set()
    for edit in edits:
        file_field = edit.get("file")
        if not file_field:
            continue
        resolved = (repo_root / file_field).resolve()
        try:
            rel = resolved.relative_to(repo_root)
        except ValueError:
            rel = Path(file_field)  # escapes repo_root — apply_edits.py rejects it; still report it
        paths.add(str(rel))
    return sorted(paths)


def _matches(path: str, glob: str) -> bool:
    # Match the full path, the path with a leading "**/" stripped (so a
    # repo-root file matches too), and the basename — so `**/evaluate.py`
    # catches evaluate.py wherever it sits and however the edit's path is written.
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
    simulator. The guard's job is different — it must never bless a submission
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


def _load_edits(editsfile: Path) -> list[dict] | None:
    """Parse the edits JSON, or print a REJECTED message and return None."""
    try:
        edits = json.loads(editsfile.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"REJECTED: could not read/parse edits file: {e}", file=sys.stderr)
        return None
    if not isinstance(edits, list):
        print("REJECTED: edits file must be a JSON list of {file, old_string, new_string}.", file=sys.stderr)
        return None
    return edits


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: check_protected_paths.py <editsfile.json>", file=sys.stderr)
        return 2
    if _resolve_config_or_reject() is None:
        return 2
    globs = get_value("protected.paths") or []
    editsfile = Path(argv[0])
    edits = _load_edits(editsfile)
    if edits is None:
        return 2
    if not globs:
        return 0  # app declares nothing protected
    paths = touched_paths(edits, Path.cwd())
    hits = protected_hits(paths, globs)
    if hits:
        print("REJECTED: edits touch protected paths (evaluator/gold/fixtures/engines/scoring):", file=sys.stderr)
        for path, glob in hits:
            print(f"  {path}  (matches {glob})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
