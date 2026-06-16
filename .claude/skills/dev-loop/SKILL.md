---
name: dev-loop
description: Full agentic development cycle — simulate → suggest → HUMAN APPROVES → implement → test → docs → repeat. The only blocking step is human approval.
allowed-tools: Bash, Read, Edit, Write, Agent, AskUserQuestion
---

# Dev Loop Orchestrator

Runs one complete feature-shipping cycle. All subagents are **read-only planners**;
this orchestrator is the **sole writer** — it applies every file change.

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
Input: "Read usage_log.jsonl and propose 2-3 features. File path: usage_log.jsonl"
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
- Include an "Other / skip this cycle" option

After the user picks, confirm the selection and proceed.

---

## STEP 4 — Implement (subagent, read-only)

Invoke the **implementer** subagent:

```
Agent: implementer
Input: "Implement: [chosen feature name and description]. Read app/main.py for context."
```

The subagent returns structured output with exact delimiters:
```
FILE: app/main.py
INSERTION_POINT: [where to add]
CODE:
```python
[code]
```

TEST_FILE: tests/test_[name].py
TEST_CODE:
```python
[test code]
```

CHANGELOG: [one-line summary]
```

**Orchestrator applies the writes:**

1. Parse `FILE:`, `INSERTION_POINT:`, `CODE:` → use **Edit** to insert the code into `app/main.py` at the described location.
2. Parse `TEST_FILE:` and `TEST_CODE:` → use **Write** to create the test file.
3. Parse `CHANGELOG:` → use **Edit** to prepend the entry under `## [Unreleased]` in `CHANGELOG.md`.

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

The subagent returns either `NO_CHANGES_NEEDED` or one or more `FIND:/REPLACE:` patches.

**Orchestrator applies patches:**
- For each `FIND:` / `REPLACE:` pair, use **Edit** on `app/main.py`.

---

## STEP 8 — Verify loop closure

```bash
python scripts/simulate.py http://localhost:8000 5
```

Confirm the new operation/endpoint appears in the simulator output under "Discovered operations".
This proves the loop closure: the simulator re-reads `/openapi.json` and exercises the new feature
without any manual editing.

---

## STEP 9 — Report & optionally repeat

Report to the user:
- What feature was implemented
- Test results (pass/fail count)
- CHANGELOG entry added
- Whether the new operation appears in the simulator

Ask: "Run another cycle?" If yes, go back to STEP 1.

---

## IMPORTANT NOTES

- **Subagents are read-only.** They return structured text only. This orchestrator applies every write.
- **Human approval (STEP 3) is the ONLY blocking step.** All other steps chain automatically.
- **Do not skip the test step.** A feature is not shipped until `pytest tests/ -v` passes.
- **Do not truncate usage_log.jsonl** — historical entries are the signal for future cycles.
