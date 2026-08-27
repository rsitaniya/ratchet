#!/usr/bin/env python3
"""The single entry point that lands the implementer's structured edits.

The implementer returns a JSON list of `{"file", "old_string", "new_string"}`
edits instead of a unified diff — the same contract as this tool's own Edit/Write
tools, which the model already has strong priors for using correctly. `old_string
== ""` means "create this new file"; otherwise `old_string` must occur exactly
once in the file's current content (or the edit is rejected). This removes an
entire failure class at the source: a diff requires the model to hand-compute
hunk headers and context lines from memory, which is mechanical bookkeeping —
exactly what this project's CLAUDE.md says not to push onto a model — and it was
the actual cause of every malformed-patch failure observed in trial runs. An
exact-substring match has no equivalent failure mode; it either matches once or
it doesn't.

Order: guard (check_protected_paths, from the edit list's file paths — no diff
parsing needed at all), then validate every edit against current file content,
then write. Validation happens for the whole batch before anything is written,
so one bad edit rejects the submission atomically rather than partially
applying. Pair with denying `Bash(git apply:*)` in `.claude/settings.json` so
this wrapper is the path of least resistance for landing a change, not just the
documented one.

This still is not an OS-level boundary: the orchestrator holds Edit/Write
directly and could bypass this entirely. What it removes is the failure mode
where the guard is skipped by omission — bypass now requires deliberate
evasion, not a forgotten step. See SECURITY.md.

Exit code: whatever check_protected_paths.py returned (2) if the guard
rejected; 1 if an edit failed validation; 0 if every edit applied.

Usage:
    python scripts/apply_edits.py <editsfile.json>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from check_protected_paths import main as check_protected_paths


class EditError(Exception):
    """One edit failed validation; nothing in the batch is written."""


def apply_edits(edits: list[dict], repo_root: Path) -> list[Path]:
    """Validate every edit against an in-memory simulation before writing any
    of them. Edits to the same file are applied in the order given, each
    against the prior edit's result, so a submission can build up one file
    across several edits and still be rejected atomically as a whole."""
    content: dict[Path, str] = {}
    for i, edit in enumerate(edits):
        file_field = edit.get("file")
        if not file_field:
            raise EditError(f"edit {i}: missing 'file'")
        path = (repo_root / file_field).resolve()
        if path != repo_root and repo_root not in path.parents:
            raise EditError(f"{file_field}: escapes the repository root")
        if "new_string" not in edit:
            raise EditError(f"{file_field}: missing 'new_string'")
        old, new = edit.get("old_string", ""), edit["new_string"]
        if old == "":
            if path in content or path.exists():
                raise EditError(f"{file_field}: create requested (old_string empty) but the file already exists")
            content[path] = new
            continue
        if path not in content:
            if not path.exists():
                raise EditError(f"{file_field}: old_string given but the file does not exist")
            content[path] = path.read_text()
        current = content[path]
        count = current.count(old)
        if count == 0:
            raise EditError(f"{file_field}: old_string not found in the current file content")
        if count > 1:
            raise EditError(f"{file_field}: old_string is not unique ({count} occurrences) — include more context")
        content[path] = current.replace(old, new, 1)

    for path, text in content.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return sorted(content)


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if not argv:
        print("usage: apply_edits.py <editsfile.json>", file=sys.stderr)
        return 2

    guard_exit = check_protected_paths(list(argv[:1]))
    if guard_exit != 0:
        return guard_exit

    editsfile = Path(argv[0])
    try:
        edits = json.loads(editsfile.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"REJECTED: could not read/parse edits file: {e}", file=sys.stderr)
        return 2

    try:
        apply_edits(edits, Path.cwd())
    except EditError as e:
        print(f"REJECTED: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
