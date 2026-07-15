---
name: dev-loop
description: One complete agentic development cycle — simulate → suggest → HUMAN APPROVES → implement → test → docs. Use `/loop /dev-loop` for the automated continuous loop.
allowed-tools: Bash, Read, Edit, Write, Agent, AskUserQuestion
---

# Dev Loop Orchestrator

Runs one complete feature-shipping cycle. All subagents are **read-only planners**;
this orchestrator is the **sole writer** — it applies every file change. For the
fully automated bonus, run this skill through Claude Code's built-in `/loop` runner:
`/loop /dev-loop`.

---

## STEP 1 — Simulate

Ensure the API server is running:

```bash
curl -s http://localhost:8000/health || echo "SERVER DOWN"
```

If the server is down, start it:

```bash
uvicorn app.main:app --reload &
sleep 2
```

Run the simulator to populate `usage_log.jsonl`:

```bash
python scripts/simulate.py http://localhost:8000 30
```

Show the current line count in the log:

```bash
wc -l usage_log.jsonl
```

---

## STEP 2 — Suggest features (subagent, read-only)

Invoke the **feature-suggester** subagent:

```
Agent: feature-suggester
Input: "Run scripts/analyze_usage.py on usage_log.jsonl, read app/main.py for currently-supported operations, and propose 2-3 features that are NOT already implemented."
```

The subagent returns a PROPOSALS block with 2-3 options, each with:
- Signal (specific numbers from the data)
- Description (one sentence)
- Complexity estimate

Capture the full PROPOSALS text.

---

## STEP 3 — HUMAN APPROVAL ⏸

**This is the only blocking step in the loop.**

Present the proposals to the user using AskUserQuestion. Show all 2-3 options
with their signal and description. Ask the user to pick one.

Do NOT proceed until the user selects a feature.

Format the question as:
- Question: "Which feature should we implement this cycle?"
- Options: one per proposal (label = feature name, description = signal + one-liner)
- Include a "Skip this cycle" option

If the user selects "Skip this cycle", end the skill cleanly. Otherwise confirm
the selection and proceed.

---

## STEP 4 — Implement (subagent, read-only)

Invoke the **implementer** subagent:

```
Agent: implementer
Input: "Implement: [chosen feature name and description]. Read app/main.py for context. Return PATCH, TEST_FILE, CHANGELOG, and EDGE_CASES."
```

The subagent returns structured output with exact delimiters:
````
PATCH:
```diff
[standard unified diff updating app/main.py and adding the TestClient test file]
```

TEST_FILE: tests/test_[name].py

CHANGELOG: [one-line summary]

EDGE_CASES: {"<op-or-feature>": [{"a": .., "b": ..}, ...]}
````

**Orchestrator applies ALL the writes (the orchestrator is the sole writer):**

1. **Code + test patch** — Extract the `PATCH:` diff into a temp file, then run `git apply --check <tempfile>`. If it passes, run `git apply <tempfile>`. If it fails, inspect the failure and either repair the diff directly or ask the implementer for a corrected unified diff.
2. **Test path sanity** — Confirm `TEST_FILE:` exists after the patch and is under `tests/`.
3. **Changelog (version-per-cycle)** — Determine the next minor version (read the current `version=` in the app module named by `[app].module` in `flywheel.toml`; bump the minor, e.g. 0.3.0 → 0.4.0). In `CHANGELOG.md`, insert a new `## [<new-version>] - <today>` section directly under `## [Unreleased]` and put the `CHANGELOG:` entry under its `### Added`. Leave `## [Unreleased]` empty.
4. **Version bump** — Use **Edit** to update the version string in every file listed in `[app].version_files` in `flywheel.toml` (by default: `app/main.py`, `pyproject.toml`, `CHANGELOG.md`) so the running app's version always matches the latest CHANGELOG release.
5. **Simulator edge cases** — Parse `EDGE_CASES:` (JSON) → use **Edit** to merge the new entry into the JSON file named by `[simulator].edge_cases` in `flywheel.toml` (by default `edge_cases.json`), so the next simulator run exercises the new feature intelligently (not just with random inputs). Keys starting with `_` are documentation and are ignored by the loader.

> The docs INSIDE the API (`/openapi.json`) are handled separately by the docs-updater in STEP 7. STEPs 3–5 above keep the *project* docs (CHANGELOG, version, simulator) in sync; STEP 7 keeps the *API* docs in sync. Both must happen every cycle.

---

## STEP 5 — Run tests

```bash
pytest tests/ -v
```

**Tests must pass before continuing.** If tests fail:
1. Read the error output carefully.
2. Fix the issue directly via Edit (do not re-invoke the implementer subagent for small fixes).
3. Re-run pytest until all tests pass.

---

## STEP 6 — Restart server to reload new routes

```bash
pkill -f "uvicorn app.main:app" 2>/dev/null || true
sleep 1
uvicorn app.main:app --reload &
sleep 2
```

Verify the new endpoint/operation appears in the live schema:

```bash
curl -s http://localhost:8000/openapi.json | python3 -c "
import json, sys
schema = json.load(sys.stdin)
print('Paths:', list(schema['paths'].keys()))
# Print enum values if Operation schema exists
op_schema = schema.get('components', {}).get('schemas', {}).get('Operation', {})
if op_schema:
    print('Operations:', op_schema.get('enum', []))
"
```

---

## STEP 7 — Update docs (subagent, read-only)

Invoke the **docs-updater** subagent:

```
Agent: docs-updater
Input: "Feature just implemented: [feature name and description]. Check app/main.py for complete OpenAPI metadata."
```

The subagent returns either `NO_CHANGES_NEEDED` or a `PATCH:` unified diff.

**Orchestrator applies patches:**
- If it returns `PATCH:`, extract the diff into a temp file and run `git apply --check <tempfile>` before `git apply <tempfile>`.
- If `git apply --check` fails, inspect the failure and repair the metadata patch directly or ask docs-updater for a corrected unified diff.

---

## STEP 8 — Verify loop closure

```bash
python scripts/simulate.py http://localhost:8000 5
```

Confirm the new feature — **whatever its shape** — shows up in the simulator's discovery
output and is then exercised. The simulator is generic: it discovers every path + method
from `/openapi.json` and synthesizes requests from their schemas, so verification is not
limited to enum `op` values. Depending on what was shipped, look for:
- a new **endpoint or method** in the `Discovered N operations: [...]` list;
- a new **enum value** on any param in the `<param> ∈ [...]` expansion lines;
- a new **query/path param or request-body field** in the per-request log (`q={...}` / `body={...}`).

If the feature appears and is hit at least once, loop closure holds: the simulator re-read
`/openapi.json` and exercised the new feature with no manual editing of the simulator.

---

## STEP 9 — Report

Report to the user:
- Cycle number (track a counter starting at 1; increment each loop)
- What feature was implemented
- Test results (pass/fail count)
- CHANGELOG entry added
- Whether the new operation appears in the simulator

This skill intentionally performs one complete cycle and exits. The fully automated
bonus is handled by Claude Code's built-in loop runner:

```text
/loop /dev-loop
```

That single command repeats this cycle until stopped. The human-approval gate in
STEP 3 is the only blocking step; press Ctrl+C or choose "Skip this cycle" to stop.

---

## IMPORTANT NOTES

- **Subagents are read-only.** They return structured text only. This orchestrator applies every write.
- **Subagent patches use standard unified diff format.** Validate with `git apply --check` before applying.
- **Human approval (STEP 3) is the ONLY blocking step.** All other steps chain automatically in each cycle.
- **Continuous mode uses Claude Code's built-in `/loop` runner.** Use `/loop /dev-loop`; stop with Ctrl+C.
- **Do not skip the test step.** A feature is not shipped until `pytest tests/ -v` passes.
- **Do not truncate usage_log.jsonl** — historical entries are the signal for future cycles.
