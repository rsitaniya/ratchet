#!/usr/bin/env python3
"""The only path that applies a patch: guard, then check, then apply — no step
in between that a caller can forget.

Before this existed, `check_protected_paths.py` was a markdown instruction the
orchestrator was asked to run before `git apply`, so "every write is guarded"
was a claim about the orchestrator's discipline, not something enforced. This
collapses the two-step prose into one entry point and one behavior. Pair it with
denying `Bash(git apply:*)` in `.claude/settings.json` so this wrapper is the
path of least resistance, not just the documented one.

This still is not an OS-level boundary: the orchestrator holds Bash and could
run `git apply` through a shell construct the deny prefix doesn't match (a `cd
x && git apply`, `sh -c ...`). What it removes is the failure mode where the
guard is skipped by omission — bypass now requires deliberate evasion, not a
forgotten step. See SECURITY.md.

Exit code is whatever check_protected_paths.py, `git apply --check`, or
`git apply` returned for the failing step; 0 only if all three succeeded.

Usage:
    python scripts/apply_patch.py <patchfile>
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from check_protected_paths import main as check_protected_paths


def apply_patch(patchfile: Path) -> int:
    guard_exit = check_protected_paths([str(patchfile)])
    if guard_exit != 0:
        return guard_exit

    check = subprocess.run(["git", "apply", "--check", str(patchfile)], capture_output=True)
    if check.returncode != 0:
        print(check.stderr.decode("utf-8", "replace"), file=sys.stderr)
        return check.returncode

    applied = subprocess.run(["git", "apply", str(patchfile)], capture_output=True)
    if applied.returncode != 0:
        print(applied.stderr.decode("utf-8", "replace"), file=sys.stderr)
    return applied.returncode


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: apply_patch.py <patchfile>", file=sys.stderr)
        return 2
    return apply_patch(Path(argv[0]))


if __name__ == "__main__":
    sys.exit(main())
