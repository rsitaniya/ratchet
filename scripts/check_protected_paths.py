#!/usr/bin/env python3
"""Reject a patch that touches protected paths (deterministic Gate-4.1 check).

The dev-loop orchestrator runs this before `git apply`. It reads the protected
globs from the active flywheel.toml (`[protected].paths`) and exits non-zero if
the patch touches any protected file. Protected paths are held-out evaluators,
gold labels, fixtures, engines, and scoring — the things the loop must never edit
to make its own metrics pass.

The touched paths come from `git apply --numstat -z`, so Git does its own
unquoting/unescaping. Parsing diff text by hand is bypassable: Git quotes paths
containing special bytes (e.g. an octal-escaped `\\145valuate.py`), and a
hand-crafted patch that quotes an all-ASCII path defeats a naive text parser
while `git apply` still writes the real file. A hardened text parse runs too, but
only as a backstop — the union of both is checked, and if Git cannot report the
targets the patch is rejected (fail closed).

Exit 0 = clean (apply is allowed). Exit 2 = a protected path was touched, the
patch could not be parsed, or usage was wrong.

Usage:
    python scripts/check_protected_paths.py <patchfile>
"""
from __future__ import annotations

import fnmatch
import subprocess
import sys
from pathlib import Path

from flywheel_config import get_value


class PatchParseError(Exception):
    """Git could not report the paths a patch touches."""


_UNESCAPE = {"a": 7, "b": 8, "t": 9, "n": 10, "v": 11, "f": 12, "r": 13, '"': 34, "\\": 92}


def _git_unquote(token: str) -> str:
    """Decode Git's C-style quoted path syntax (`core.quotePath`).

    Git wraps paths with special bytes in double quotes and escapes them with
    backslash sequences (`\\t`, `\\"`, `\\\\`) or octal byte escapes (`\\145`).
    A path that is not quoted is returned unchanged. Decoding to bytes first,
    then UTF-8, is why this matches what `git apply` actually writes.
    """
    token = token.strip()
    if len(token) < 2 or token[0] != '"' or token[-1] != '"':
        return token
    body, out, i = token[1:-1], bytearray(), 0
    while i < len(body):
        c = body[i]
        if c == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            if nxt in "01234567":
                digits = ""
                j = i + 1
                while j < len(body) and len(digits) < 3 and body[j] in "01234567":
                    digits += body[j]
                    j += 1
                out.append(int(digits, 8))
                i = j
            else:
                out.append(_UNESCAPE.get(nxt, ord(nxt)))
                i += 2
        else:
            out.extend(c.encode("utf-8"))
            i += 1
    return out.decode("utf-8", "surrogateescape")


def _strip_prefix(p: str) -> str:
    p = _git_unquote(p.strip())
    if p.startswith(("a/", "b/")):
        p = p[2:]
    return p


def all_touched_paths(patchfile: Path) -> set[str]:
    """Every path the patch could touch — the set the guard checks.

    Union of two detections so neither's blind spot is exploitable:
    `git apply --numstat -z` (authoritative, Git-unquoted) for adds, deletes,
    modifies, and rename *destinations*; and an unquoted text parse for rename
    and copy *sources*, which numstat collapses away. Raises PatchParseError if
    Git cannot parse the patch, so the caller can fail closed.
    """
    paths = set(paths_touched(patchfile))
    paths |= set(changed_paths(patchfile.read_text(errors="replace")))
    return paths


def paths_touched(patchfile: Path) -> list[str]:
    """Paths per `git apply --numstat -z` — authoritative but rename-source-blind.

    Git emits raw NUL-terminated paths, so it handles the quoting/escaping a text
    parser gets wrong. This does not touch the working tree — numstat only parses
    the patch. Note: a pure rename reports only its destination, so callers must
    union this with the text parse (see `all_touched_paths`).
    """
    proc = subprocess.run(
        ["git", "apply", "--numstat", "-z", str(patchfile)],
        capture_output=True,
    )
    if proc.returncode != 0:
        raise PatchParseError(proc.stderr.decode("utf-8", "replace").strip())
    return _parse_numstat_z(proc.stdout)


def _parse_numstat_z(blob: bytes) -> list[str]:
    """Parse `git apply --numstat -z` output.

    Each record is `<added>\\t<removed>\\t` followed by the path and a NUL. For a
    rename/copy the stat prefix ends in a tab and is immediately followed by NUL,
    then the old path (NUL) and new path (NUL) as separate tokens.
    """
    tokens = blob.split(b"\0")
    paths: set[str] = set()
    k = 0
    while k < len(tokens):
        t = tokens[k]
        if t.count(b"\t") >= 2:
            after = t.split(b"\t", 2)[2]
            if after == b"":  # rename/copy — next two tokens are old, new
                for j in (k + 1, k + 2):
                    if j < len(tokens) and tokens[j]:
                        paths.add(tokens[j].decode("utf-8", "surrogateescape"))
                k += 3
                continue
            paths.add(after.decode("utf-8", "surrogateescape"))
        k += 1
    return sorted(paths)


def changed_paths(diff_text: str) -> list[str]:
    """Backstop text parse of a unified diff — both sides, incl. renames/copies.

    Kept as defense in depth alongside `paths_touched`; not the security
    boundary on its own (it cannot reliably undo Git's path quoting).
    """
    paths: set[str] = set()
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            rest = line[len("diff --git "):]
            if " b/" in rest:
                a_part, b_part = rest.split(" b/", 1)
                paths.add(_strip_prefix(a_part))
                paths.add(_strip_prefix("b/" + b_part))
        elif line.startswith(("--- ", "+++ ")):
            body = line[4:].strip()
            if body != "/dev/null":
                paths.add(_strip_prefix(body))
        elif line.startswith(("rename from ", "rename to ", "copy from ", "copy to ")):
            paths.add(_strip_prefix(line.split(" ", 2)[2]))
    return sorted(paths)


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


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: check_protected_paths.py <patchfile>", file=sys.stderr)
        return 2
    globs = get_value("protected.paths") or []
    if not globs:
        return 0  # app declares nothing protected
    patchfile = Path(argv[0])
    try:
        paths = all_touched_paths(patchfile)
    except PatchParseError as e:
        print("REJECTED: git could not determine the patch's targets, so it cannot be", file=sys.stderr)
        print(f"  proven safe: {e}", file=sys.stderr)
        return 2  # fail closed — an unparseable patch is not a clean patch
    hits = protected_hits(sorted(paths), globs)
    if hits:
        print("REJECTED: patch touches protected paths (evaluator/gold/fixtures/engines/scoring):", file=sys.stderr)
        for path, glob in hits:
            print(f"  {path}  (matches {glob})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
