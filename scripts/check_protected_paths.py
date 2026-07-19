#!/usr/bin/env python3
"""Reject a patch that touches protected paths (deterministic Gate-4.1 check).

The dev-loop orchestrator runs this before `git apply`. It reads the protected
globs from the active flywheel.toml (`[protected].paths`), extracts the files a
unified diff touches, and exits non-zero if any is protected. Protected paths are
held-out evaluators, gold labels, fixtures, and scoring — the things the loop must
never edit to make its own metrics pass.

Exit 0 = clean (apply is allowed). Exit 2 = a protected path was touched.

Usage:
    python scripts/check_protected_paths.py <patchfile>
"""
from __future__ import annotations

import fnmatch
import sys
from pathlib import Path

from flywheel_config import get_value


def _strip_prefix(p: str) -> str:
    p = p.strip()
    if p.startswith(("a/", "b/")):
        p = p[2:]
    return p


def changed_paths(diff_text: str) -> list[str]:
    """Every path a diff references, on BOTH sides.

    Covers plain edits (`+++ b/…`), additions/deletions (`--- a/…`, ignoring
    `/dev/null`), and — critically — renames, which carry no `+++`/`---` lines at
    all. A patch that renames or deletes a protected file must be caught too, so
    we union the old and new paths from the `diff --git` header and the
    `rename from`/`rename to` lines. Missing any of these is a bypass.
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
    paths = changed_paths(Path(argv[0]).read_text())
    hits = protected_hits(paths, globs)
    if hits:
        print("REJECTED: patch touches protected paths (evaluator/gold/fixtures/scoring):", file=sys.stderr)
        for path, glob in hits:
            print(f"  {path}  (matches {glob})", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
