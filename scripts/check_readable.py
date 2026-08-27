#!/usr/bin/env python3
"""PreToolUse read guard, scoped to the implementer subagent.

Wired from `.claude/agents/implementer.md`'s own `hooks:` frontmatter, so it runs
only while that subagent is active and is torn down when it finishes. That scope
is the point. The previous mechanism was a `permissions.deny` block in
`.claude/settings.json`, which is session-wide: it also blocked the orchestrator
and any human session in this repo from reading `runs/`, which they legitimately
need (Gate 2 shows receipts; the trial skill writes a trial report it then could
not read back). Claude Code's subagent frontmatter has no path-scoped
`permissions` block — `tools:`/`disallowedTools:` are tool-level, not
path-level — so a `PreToolUse` hook is the mechanism that expresses "this one
agent cannot read these paths."

The globs come from `[protected].unreadable` in the active flywheel.toml, not
from a second hand-maintained list. `[protected].paths` (unwritable) stays
separate on purpose: the implementer must read `adapters.py` and the app source
it edits against, and must never read gold, fixtures, or a prior cycle's
converged receipt.

Matcher is `Read|Grep` only. `Glob` stays allowed: the implementer is meant to
see the shape of the tree, just never the contents of an answer key.

A directory read is checked by walking it, not by matching the directory name.
Otherwise `Grep(path="engagements/madi_onboarding")` would walk straight past a
`**/fixtures/**` glob that never matches the parent — a guard with that hole is
theatre, and this repo's own rule is that boundaries get validated adversarially.
A call that names no path at all is judged as the working directory, because that
is what the tool itself would search: `Grep(pattern=...)` with no `path` is an
easier reach for gold than any parent directory, and treating "no path" as
"nothing to judge" is the fail-open version of the same bug.

Fails closed: if no config resolves, every read is denied rather than blessed.
Same reasoning as check_protected_paths.py — "nobody configured protection" must
never read as "nothing is protected".

That fail-closed state is total, and deliberately so: it denies ordinary app
source too, which leaves the implementer unable to do anything at all. Loosening
it would mean guessing which engagement is active, and guessing wrong picks
another engagement's unreadable list. The right place to catch this is before the
cycle starts, so /dev-loop STEP 1 refuses to run when FLYWHEEL_CONFIG is missing
from Claude Code's own environment.

Exit 0 = allowed. Exit 2 = denied (Claude Code blocks the call and shows stderr).

Usage (as a hook; hook JSON arrives on stdin):
    python scripts/check_readable.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from check_protected_paths import matches_glob
from flywheel_config import config_path, get_value

# Where each guarded tool puts the thing it is about to read.
PATH_FIELDS = ("file_path", "path", "notebook_path")

# Never worth walking, and never where gold lives.
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", ".pytest_cache", ".ruff_cache"}


def requested_paths(tool_input: dict) -> list[str]:
    """The paths a Read/Grep call is asking for, in the order the tool names them.

    An unnamed target is the working directory, not nothing. `Grep(pattern=...)`
    with no `path` is the tool's own default and searches the whole repo, so
    returning [] here would fail OPEN on the cheapest possible reach for gold —
    strictly easier than the `Grep(parent_dir)` case this guard was written to
    close. Same rule as everywhere else in this repo: a target the guard cannot
    name is denied, never blessed.
    """
    named = [str(tool_input[f]) for f in PATH_FIELDS if tool_input.get(f)]
    return named or ["."]


def _candidates(target: Path) -> list[Path]:
    """Files a read of `target` could actually surface.

    A file is itself; a directory is every file under it (that is what Grep
    reads); a path that does not exist is judged literally, so a guard decision
    never depends on whether the file happens to be present yet.
    """
    if target.is_dir():
        return [
            p for p in target.rglob("*")
            if p.is_file() and not SKIP_DIRS & set(p.parts)
        ]
    return [target]


def blocked_hits(paths: list[str], globs: list[str], repo_root: Path) -> list[str]:
    """Repo-relative paths among `paths` (or reachable under them) that are unreadable."""
    hits: list[str] = []
    for raw in paths:
        target = (repo_root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
        for candidate in _candidates(target):
            try:
                rel = str(candidate.resolve().relative_to(repo_root))
            except ValueError:
                # Outside the repo entirely: no engagement glob can describe it,
                # and the tool grant is what bounds that case, not this guard.
                continue
            if any(matches_glob(rel, g) for g in globs):
                hits.append(rel)
    return sorted(set(hits))


def main(stdin=None) -> int:
    stdin = stdin if stdin is not None else sys.stdin
    try:
        payload = json.load(stdin)
    except (OSError, json.JSONDecodeError) as e:
        print(f"DENIED: could not parse hook payload: {e}", file=sys.stderr)
        return 2

    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        print("DENIED: hook payload has no usable tool_input.", file=sys.stderr)
        return 2

    paths = requested_paths(tool_input)

    try:
        cfg = config_path()
    except FileNotFoundError as e:
        print(f"DENIED: {e}", file=sys.stderr)
        return 2
    if not cfg.exists():
        print(f"DENIED: no flywheel.toml resolved (looked for {cfg}).", file=sys.stderr)
        print("  This hook inherits Claude Code's own environment, so FLYWHEEL_CONFIG", file=sys.stderr)
        print("  must be exported BEFORE launching Claude Code — a Bash step's export", file=sys.stderr)
        print("  does not reach it. Relaunch as:", file=sys.stderr)
        print("    export FLYWHEEL_CONFIG=engagements/<name>/flywheel.toml && claude", file=sys.stderr)
        return 2

    globs = get_value("protected.unreadable") or []
    if not globs:
        return 0  # engagement declares nothing held out from reading

    hits = blocked_hits(paths, globs, Path.cwd().resolve())
    if hits:
        print(f"DENIED: {payload.get('tool_name', 'read')} reaches held-out material:", file=sys.stderr)
        for hit in hits[:10]:
            print(f"  {hit}", file=sys.stderr)
        if len(hits) > 10:
            print(f"  ... and {len(hits) - 10} more", file=sys.stderr)
        print("  Derive the mapping from the source records' own shape, not an answer key.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
