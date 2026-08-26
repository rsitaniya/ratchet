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

**Precondition: the working tree must be clean.** This cycle applies patches and,
on a Gate-2 revert, discards every uncommitted change to restore the pre-cycle
state. If the tree already has uncommitted work, that revert would destroy it, so
refuse to start:

```bash
if [ -n "$(git status --porcelain)" ]; then
  echo "ABORT: working tree is dirty. Commit or stash before running the loop."; exit 1
fi
```

Everything domain-specific comes from the active `flywheel.toml` (selected by
`$FLYWHEEL_CONFIG`, else the repo-root file). Read the app module, base URL, and
usage-log path from it rather than hardcoding — that is what lets this one loop
drive any app.

**Snapshot the evaluator baseline now, while the tree is still the pre-cycle
state** (the precondition above just proved it's clean). This is what makes the
Gate-2 regression check in STEP 6 possible — without a baseline captured *before*
the patch lands, there is nothing to compare against:

```bash
EVALUATOR=$(uv run python scripts/flywheel_config.py --get app.evaluator)
rm -f .dev_loop_baseline.json
if [ -n "$EVALUATOR" ]; then
  eval "$EVALUATOR" > .dev_loop_baseline.json   # eval, not bare $EVALUATOR — zsh does not word-split unquoted vars
fi
```

Empty for apps without one — the file is simply absent and
STEP 6 skips the comparison. `.dev_loop_baseline.json` is gitignored scratch state,
not a repo artifact.

Ensure the API server is running:

```bash
BASE_URL=$(uv run python scripts/flywheel_config.py --get app.base_url)
curl -s "$BASE_URL/health" || echo "SERVER DOWN"
```

If the server is down, start it (exporting the config's usage-log path so the
server, simulator, and analyzer all agree on one file):

```bash
export USAGE_LOG_PATH=$(uv run python scripts/flywheel_config.py --get app.usage_log)
uv run uvicorn "$(uv run python scripts/flywheel_config.py --get app.module)" --reload &
sleep 2
```

Run the simulator (no args → it reads the base URL and request count from config):

```bash
uv run python scripts/simulate.py
```

Show the current line count in the log:

```bash
wc -l "$(uv run python scripts/flywheel_config.py --get app.usage_log)"
```

---

## STEP 2 — Suggest features (subagent, read-only)

Resolve paths from config and **run the analyzer yourself** — the feature-suggester
is a read-only planner with no shell, so you produce its input. The analyzer command
comes from config (`app.analyzer`), defaulting to the generic HTTP analyzer; an
engagement points it at its own domain gap-ranker:

```bash
USAGE_LOG=$(uv run python scripts/flywheel_config.py --get app.usage_log)
ANALYZER=$(uv run python scripts/flywheel_config.py --get app.analyzer)   # empty → generic
REPORT=$(${ANALYZER:-uv run python scripts/analyze_usage.py} "$USAGE_LOG")
uv run python scripts/flywheel_config.py --get app.module   # e.g. myservice.api:app → myservice/api.py
```

Invoke the **feature-suggester** subagent, passing the report inline:

```
Agent: feature-suggester
Input: "Signal report:\n<the $REPORT text>\n\nRead <app source file from config> for currently-supported functionality, and propose 2-3 features that are NOT already implemented."
```

The subagent returns a PROPOSALS block with 2-3 options, each with:
- Signal (specific numbers from the data)
- Description (one sentence)
- Complexity estimate

Capture the full PROPOSALS text.

---

## STEP 3 — HUMAN APPROVAL: GATE 1 (approve the proposal) ⏸

**The loop has two human gates. This is the first: approving *what* to build.**
(Gate 2, in STEP 6, approves the *exact tested tree* before it is kept.)

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
Input: "Implement: [chosen feature name and description]. Read <app source file from config> for context (its import path is <app.module from config>). Return PATCH, TEST_FILE, CHANGELOG, and EDGE_CASES."
```

The subagent returns structured output with exact delimiters:
````
PATCH:
```diff
[standard unified diff updating the app source module and adding the TestClient test file]
```

TEST_FILE: tests/test_[name].py

CHANGELOG: [one-line summary]

EDGE_CASES: {"<op-or-feature>": [{"a": .., "b": ..}, ...]}
````

**Orchestrator applies ALL the writes (the orchestrator is the sole writer):**

1. **Code + test patch** — Extract the `PATCH:` diff into a temp file.
   - **Protected-path check (do this BEFORE `git apply --check`).** Run the deterministic checker on the patch:
     ```bash
     uv run python scripts/check_protected_paths.py <tempfile>
     ```
     Exit 0 = clean, proceed. **Exit 2 = the patch touches a protected path** (held-out evaluator, gold labels, fixtures, scoring — read from `[protected].paths` in the active config). **REJECT the patch** — do not apply it — and ask the implementer to resubmit without touching protected files. This is what stops the loop from gaming its own test. Apps that declare no `[protected]` paths always pass.
   - Then run `git apply --check <tempfile>`. If it passes, run `git apply <tempfile>`. If it fails, inspect the failure and either repair the diff directly or ask the implementer for a corrected unified diff.
2. **Test path sanity** — Confirm `TEST_FILE:` exists after the patch and is under `tests/`.
3. **Changelog (version-per-cycle)** — Determine the next minor version (read the current `version=` in the app module named by `[app].module` in `flywheel.toml`; bump the minor, e.g. 0.3.0 → 0.4.0). In `CHANGELOG.md`, insert a new `## [<new-version>] - <today>` section directly under `## [Unreleased]` and put the `CHANGELOG:` entry under its `### Added`. Leave `## [Unreleased]` empty.
4. **Version bump** — Use **Edit** to update the version string in every file listed in `[app].version_files` in the active `flywheel.toml` so the running app's version always matches the latest CHANGELOG release.
5. **Simulator edge cases** — Parse `EDGE_CASES:` (JSON) → use **Edit** to merge the new entry into the JSON file named by `[simulator].edge_cases` in `flywheel.toml` (by default `edge_cases.json`), so the next simulator run exercises the new feature intelligently (not just with random inputs). Keys starting with `_` are documentation and are ignored by the loader.

> The docs INSIDE the API (`/openapi.json`) are handled separately by the docs-updater in STEP 5.5. STEPs 3–5 above keep the *project* docs (CHANGELOG, version, simulator) in sync; STEP 5.5 keeps the *API* docs in sync. Both must happen every cycle.

---

## STEP 5 — Run tests

```bash
uv run pytest tests/ -v
```

**Tests must pass before continuing.** If tests fail:
1. Read the error output carefully.
2. Fix the issue directly via Edit (do not re-invoke the implementer subagent for small fixes).
3. Re-run `uv run pytest` until all tests pass.

---

## STEP 5.5 — Update API docs (subagent, read-only)

Invoke the **docs-updater** subagent BEFORE the approval gate, so the human
approves — and the evaluator scores — the complete final tree, not a partial one.

```
Agent: docs-updater
Input: "Feature just implemented: [feature name and description]. Check <app source file from config> for complete OpenAPI metadata."
```

The subagent returns either `NO_CHANGES_NEEDED` or a `PATCH:` unified diff.

**Orchestrator applies the patch under the SAME guard as every other patch —
a docs patch is not exempt:**
- If it returns `PATCH:`, extract the diff into a temp file and run
  `uv run python scripts/check_protected_paths.py <tempfile>` FIRST. **Exit 2 = the patch
  touches a protected path → REJECT it** and ask docs-updater to resubmit. On
  exit 0, run `git apply --check <tempfile>` then `git apply <tempfile>`.
- If `git apply --check` fails, repair the metadata patch directly or ask
  docs-updater for a corrected unified diff.

---

## STEP 6 — HUMAN APPROVAL: GATE 2 (approve the exact tested tree) ⏸

**The second gate, and it runs after every edit this cycle — code, tests,
changelog, version, edge cases, and docs are all applied by now.** Approving what
to build (Gate 1) does not authorize whatever the implementer produced. An agent
can make tests pass by weakening them; a held-out evaluator plus a human reading
the actual diff are what catch that.

1. **Run the app's evaluator, if it declares one, against the pre-cycle baseline STEP 1 captured.**
   ```bash
   EVALUATOR=$(uv run python scripts/flywheel_config.py --get app.evaluator)
   if [ -n "$EVALUATOR" ]; then
     if [ -s .dev_loop_baseline.json ]; then
       eval "$EVALUATOR --baseline .dev_loop_baseline.json"
     else
       eval "$EVALUATOR"   # no baseline on record (e.g. first-ever cycle) — score only
     fi
   fi
   ```
   Empty `app.evaluator` → no evaluator declared — skip to step 2.
   Capture the machine-readable result. **If it reports `"regression": true`, this is a
   hard failure — treat it exactly like a failing test, not something to note and
   proceed past.** Do not show it to the human as a pass. Go straight to Revert
   (below), or fix the patch and re-run STEP 5 onward. A regression means the loop
   improved the new source by silently breaking one that already worked — for an
   onboarding system that is the worst failure mode there is, so it blocks the gate
   the same way a failing test does.
2. **Show the human the exact change.** Present the diff hash (`git diff | git hash-object --stdin`), the changed-file list, the diff (or a tight summary if large), and the evaluator result. Use AskUserQuestion: "Keep this patch? (Gate 2)" with options Keep / Revert.
3. **On Revert:** restore the pre-cycle tree, report why, and end the cycle cleanly. Because STEP 1 refused to start on a dirty tree, everything uncommitted belongs to this cycle, so `git checkout -- .` followed by `git clean -fd` is safe — gitignored runtime files (e.g. the usage log) are preserved. **On Keep:** proceed.

Do NOT proceed past this gate without an explicit Keep. For an app with no
evaluator and no `[protected]` paths this is a quick visual confirm of the
diff; for an engagement with a protected evaluator it is the real safety boundary.

---

## STEP 7 — Restart server to reload new routes

```bash
APP=$(uv run python scripts/flywheel_config.py --get app.module)
pkill -f "uvicorn $APP" 2>/dev/null || true
sleep 1
export USAGE_LOG_PATH=$(uv run python scripts/flywheel_config.py --get app.usage_log)
uv run uvicorn "$APP" --reload &
sleep 2
```

Verify the new endpoint/operation appears in the live schema:

```bash
BASE_URL=$(uv run python scripts/flywheel_config.py --get app.base_url)
curl -s "$BASE_URL/openapi.json" | uv run python3 -c "
import json, sys
schema = json.load(sys.stdin)
print('Paths:', list(schema['paths'].keys()))
# Surface any enum-valued params generically (e.g. an op enum), whatever the app.
for name, comp in schema.get('components', {}).get('schemas', {}).items():
    if isinstance(comp, dict) and comp.get('enum'):
        print(f'{name} enum:', comp['enum'])
"
```

---

## STEP 8 — Verify loop closure

```bash
uv run python scripts/simulate.py "$(uv run python scripts/flywheel_config.py --get app.base_url)" 5
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

That single command repeats this cycle until stopped. The human gates (STEP 3
and STEP 6) are the blocking steps; press Ctrl+C or choose "Skip this cycle"
to stop.

---

## IMPORTANT NOTES

- **Subagents are read-only.** They return structured text only. This orchestrator applies every write.
- **Subagent patches use standard unified diff format.** Validate with `git apply --check` before applying.
- **Two human gates block the loop: STEP 3 (approve the proposal) and STEP 6 (approve the exact tested tree).** All other steps chain automatically.
- **Every applied patch — code, docs, anything — passes `check_protected_paths.py` before `git apply`.** No patch is exempt. The evaluator and Gate 2 run only after all edits are applied, so they judge the final tree.
- **The implementer may never touch protected paths** (held-out evaluators, gold, fixtures, scoring). The orchestrator rejects such patches before applying (STEP 4.1). This is enforcement, not etiquette, for the implementer specifically: it holds no Bash, so its diff is its only mutation path, and every diff passes the guard. The orchestrator's own direct edits (STEP 4.3-4.5: CHANGELOG, version files, `edge_cases.json`) skip the diff-based guard — those three files are never protected-path candidates in any shipped config, so there is nothing for that skip to reach, but it means "every write is guarded" is a claim about the implementer's contract, not a kernel-level boundary on the orchestrator itself.
- **Continuous mode uses Claude Code's built-in `/loop` runner.** Use `/loop /dev-loop`; stop with Ctrl+C.
- **Do not skip the test step.** A feature is not shipped until `uv run pytest tests/ -v` passes.
- **Do not truncate the usage log** — historical entries are the signal for future cycles.
