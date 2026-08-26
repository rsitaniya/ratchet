---
name: dev-loop
description: One complete agentic development cycle — simulate → propose → HUMAN APPROVES → implement → test → HUMAN APPROVES. Use `/loop /dev-loop` for the automated continuous loop.
allowed-tools: Bash, Read, Edit, Write, Agent, AskUserQuestion
---

# Dev Loop Orchestrator

Runs one complete feature-shipping cycle. The **implementer** subagent is a
**read-only planner** — it returns a diff and cannot write files; this
orchestrator is the **sole writer** — it applies every file change. For the
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

**Echo and confirm the resolved config before anything else runs.** A run with
no config resolved has an empty `[protected].paths`, so `check_protected_paths.py`
now refuses to bless any patch until a real config is confirmed (see STEP 4) —
but that refusal should not be the operator's first signal that `$FLYWHEEL_CONFIG`
was wrong or unset. Surface it up front instead:

```bash
if ! MODULE=$(uv run python scripts/flywheel_config.py --get app.module); then
  echo "ABORT: could not resolve the active config (see error above). Check \$FLYWHEEL_CONFIG."; exit 1
fi
echo "Active config: ${FLYWHEEL_CONFIG:-<none set — falls back to defaults, no engagement selected>}"
echo "App module: $MODULE"
```

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

## STEP 2 — Propose features from the signal report

Every shipped engagement declares its own domain analyzer (`[app].analyzer`) — the
generic per-endpoint HTTP analyzer this repo shipped alongside the calculator
example is gone along with that example, so `app.analyzer` is required, not
optional:

```bash
USAGE_LOG=$(uv run python scripts/flywheel_config.py --get app.usage_log)
ANALYZER=$(uv run python scripts/flywheel_config.py --get app.analyzer)
if [ -z "$ANALYZER" ]; then
  echo "ABORT: [app].analyzer is not set in the active flywheel.toml."; exit 1
fi
REPORT=$(eval "$ANALYZER" "$USAGE_LOG")
```

Read `<app source file from config>` for what is already supported (existing
endpoints, enums, request/response models — the current schema), then propose
2-3 features grounded in the signal report:

- Cite a specific number from `$REPORT` for each proposal (a count, a
  percentage, a ratio) — a proposal that cannot point at data in the report is
  not grounded.
- Never re-propose something the app already implements — check the app source
  first.
- Prefer low-complexity proposals; this is a time-boxed exercise.

There is no dedicated subagent for this step: producing 2-3 sentences from a
report you just generated, for a human to choose between at Gate 1, does not
need an isolated context or a restricted tool grant — you already hold the
report and the app source, and a subagent here would only reformat what you
already have. State the 2-3 proposals (name, signal, one-line description,
complexity estimate) directly.

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
Input: "Implement: [chosen feature name and description]. Read <app source file from config> for context (its import path is <app.module from config>). Return PATCH, TEST_FILE, and CHANGELOG."
```

The subagent returns structured output with exact delimiters:
````
PATCH:
```diff
[standard unified diff updating the app source module and adding the TestClient test file]
```

TEST_FILE: tests/test_[name].py

CHANGELOG: [one-line summary]
````

**Orchestrator applies ALL the writes (the orchestrator is the sole writer):**

1. **Code + test patch** — Extract the `PATCH:` diff into a temp file, then run:
   ```bash
   uv run python scripts/apply_patch.py <tempfile>
   ```
   This is the only path that applies a patch: it runs the protected-path guard,
   `git apply --check`, and `git apply` in that fixed order, so there is no step
   to skip and no way for a patch to reach the tree without passing the guard
   first. **Exit 2 from the guard stage = the patch touches a protected path**
   (held-out evaluator, gold labels, fixtures, `runs/`, scoring — read from
   `[protected].paths` in the active config) — **REJECT the patch** and ask the
   implementer to resubmit without touching protected files. A nonzero exit
   from the `git apply --check`/`git apply` stage means the diff itself is bad —
   inspect the failure and either repair it directly or ask the implementer for
   a corrected unified diff.
2. **Test path sanity** — Confirm `TEST_FILE:` exists after the patch and is under `tests/`.
3. **Changelog** — In `CHANGELOG.md`, insert (or append to) a `## [Unreleased]`
   entry under `### Added` with the `CHANGELOG:` line.
4. **Version bump (only if `[app].version_files` is non-empty)** — Most cycles
   change a few lines of adapter or rule TOML; treat a version release as a
   deliberate operator action, not something every cycle pays for. When
   `version_files` is set: determine the next minor version (read the current
   `version=` from `[app].module`; bump the minor), move the `## [Unreleased]`
   section to `## [<new-version>] - <today>`, and use **Edit** to update the
   version string in every file listed in `[app].version_files`.

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

## STEP 6 — HUMAN APPROVAL: GATE 2 (approve the exact tested tree) ⏸

**The second gate, and it runs after every edit this cycle — code, tests,
changelog, and (when applicable) version are all applied by now.** Approving
what to build (Gate 1) does not authorize whatever the implementer produced. An
agent can make tests pass by weakening them; a held-out evaluator plus a human
reading the actual diff are what catch that.

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

- **One subagent, `implementer`, and its restriction is mechanical, not procedural.**
  It holds `Read, Grep, Glob` — no Bash, no Edit, no Write — so a returned diff
  is its *only* possible mutation path, and Claude Code's own deny rules block
  it from reading fixtures, gold, or `runs/` at the tool level (not just by
  instruction). Feature proposal (STEP 2) does not warrant a second subagent:
  the orchestrator already holds the signal report and the app source that
  step needs, and a subagent there would only reformat what it already has —
  its output is a few sentences a human chooses between at Gate 1, which is not
  an isolation boundary worth a round-trip. Everything past the implementer's
  diff is deterministic code (`apply_patch.py`, the evaluator, tests) or a
  human at one of the two gates.
- **Every patch — always, no exceptions — goes through `scripts/apply_patch.py`,
  never `git apply` directly.** That script *is* the guard: it runs the
  protected-path check, `git apply --check`, and `git apply`, in that order,
  with no path that skips any of the three. `.claude/settings.json` also denies
  `Bash(git apply:*)` directly, so `apply_patch.py` is the path of least
  resistance, not just the documented one. This is a stronger claim than "every
  write is guarded" used to be — there is no longer a category of orchestrator
  edit (CHANGELOG, version bump) that bypasses it, because those edits use Edit,
  not `git apply`, and were never diff-based to begin with. **What this is not:**
  an OS-level boundary. The orchestrator holds Bash and could still reach `git
  apply` through a shell construct the deny prefix doesn't match. What changed
  is the failure mode — bypassing the guard now requires deliberate evasion,
  not a forgotten step. See `SECURITY.md`.
- **Two human gates block the loop: STEP 3 (approve the proposal) and STEP 6
  (approve the exact tested tree).** All other steps chain automatically.
- **`check_protected_paths.py` (run inside `apply_patch.py`) refuses to run at
  all if no `flywheel.toml` resolves** — a missing config is not the same as a
  config that declares nothing protected, and blessing a patch because no one
  configured protection would be the guard's own version of the bug it exists
  to prevent. STEP 1 echoes the resolved config up front so this is never the
  operator's first signal that `$FLYWHEEL_CONFIG` was wrong.
- **Continuous mode uses Claude Code's built-in `/loop` runner.** Use `/loop /dev-loop`; stop with Ctrl+C.
- **Do not skip the test step.** A feature is not shipped until `uv run pytest tests/ -v` passes.
- **Do not truncate the usage log** — historical entries are the signal for future cycles.
