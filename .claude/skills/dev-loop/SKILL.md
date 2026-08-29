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

**First, check the config the way the implementer's hook will see it.** This is
its own step because it catches a failure nothing else does. The implementer's
read guard runs as a `PreToolUse` hook, and a hook inherits *Claude Code's own*
environment — not what a Bash step exports, because shell state does not persist
between tool calls. So a cycle can look perfectly configured at every step below
and still hand the implementer a guard that fails closed and denies every read,
including the app source it must read to produce any edits at all. Run this in a
Bash call with no `export` before it, or it proves nothing:

```bash
if [ -z "$FLYWHEEL_CONFIG" ]; then
  echo "ABORT: FLYWHEEL_CONFIG is not set in Claude Code's own environment."
  echo "  Every step below can still resolve it, but the implementer's read-guard"
  echo "  hook cannot — it will fail closed and deny every Read and Grep it makes,"
  echo "  including the app source it needs. Exit, export it, and relaunch:"
  echo "    export FLYWHEEL_CONFIG=engagements/<name>/flywheel.toml && claude"
  exit 1
fi
echo "Read guard will resolve: $FLYWHEEL_CONFIG"
```

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

**Open the cycle's delivery record.** This is what makes the loop's own cost
measurable instead of asserted — every `mark` below stamps a clock, and the
record lands under `[app].cycle_log` at STEP 6. Never compute a duration
yourself; that is the same mechanical bookkeeping the structured-edit contract
exists to keep away from a model.

```bash
CYCLE=1   # increment per cycle; see STEP 9
uv run python scripts/cycle_log.py start --cycle "$CYCLE" --gates human
```

Ensure the API server is running:

```bash
BASE_URL=$(uv run python scripts/flywheel_config.py --get app.base_url)
curl -s "$BASE_URL/health" || echo "SERVER DOWN"
```

If the server is down, start it. Export the config's usage-log path so the
server, simulator, and analyzer all agree on one file, and — only when the
active config sets them (real-split configs do; the synthetic default does
not, and an empty-string export would override the app's own default) — its
adapters dir and target schema, or the app silently serves the wrong split's
adapters:

```bash
export USAGE_LOG_PATH=$(uv run python scripts/flywheel_config.py --get app.usage_log)
ADAPTERS_DIR_VAL=$(uv run python scripts/flywheel_config.py --get app.adapters_dir)
[ -n "$ADAPTERS_DIR_VAL" ] && export ADAPTERS_DIR="$ADAPTERS_DIR_VAL"
TARGET_SCHEMA_VAL=$(uv run python scripts/flywheel_config.py --get app.target_schema)
[ -n "$TARGET_SCHEMA_VAL" ] && export TARGET_SCHEMA_PATH="$TARGET_SCHEMA_VAL"
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
uv run python scripts/cycle_log.py mark simulate
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
uv run python scripts/cycle_log.py mark analyze
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

If the user selects "Skip this cycle", close the cycle record and end the skill
cleanly:

```bash
uv run python scripts/cycle_log.py mark gate1
uv run python scripts/cycle_log.py finish --outcome skipped
```

Otherwise confirm the selection, stamp the gate, and proceed. The `gate1` mark
goes in **after** the human answers — its duration is how long the human took,
which is half the delivery-cost number this loop claims:

```bash
uv run python scripts/cycle_log.py mark gate1
```

---

## STEP 4 — Implement (subagent, read-only)

Invoke the **implementer** subagent:

```
Agent: implementer
Input: "Implement: [chosen feature name and description]. Read <app source file from config> for context (its import path is <app.module from config>). Return EDITS, TEST_FILE, VERIFICATION, and LIMITS."
```

The subagent returns structured output with exact delimiters:
````
EDITS:
```json
[
  {"file": "path/to/file.toml", "old_string": "exact existing text", "new_string": "its replacement"},
  {"file": "tests/test_feature.py", "old_string": "", "new_string": "complete content of a new file"}
]
```

TEST_FILE: tests/test_[name].py

VERIFICATION:
| target | source column | normalizer | real value tried | result |
|---|---|---|---|---|

LIMITS:
- <what this change does not do>
````

**Read `VERIFICATION` before you apply anything.** It is one row per field the change
maps, tracing a real source value through the chosen normalizer. **Any row whose result
is an error is a hard stop**: that field is declared but produces nothing, which is the
exact shape of the one bad change this loop has landed — a mapping that raised the
schema score while normalizing zero records. Reject the submission and ask for a
resubmission that either extends the normalizer or drops the field to `LIMITS`. Do not
"note it and proceed", and do not repair it yourself.

An empty or missing `VERIFICATION` on a change that maps data is also a rejection. The
whole point of the block is that a dead mapping cannot be submitted without writing down
that it is dead.

Keep `VERIFICATION` and `LIMITS` for STEP 6 — both are shown to the human at Gate 2.

**Orchestrator applies ALL the writes (the orchestrator is the sole writer):**

Stamp the subagent round-trip as soon as it returns, before applying anything:

```bash
uv run python scripts/cycle_log.py mark implement
```

1. **Code + test edits** — Extract the `EDITS:` JSON into a temp file, then run:
   ```bash
   uv run python scripts/apply_edits.py <tempfile>
   uv run python scripts/cycle_log.py mark apply
   ```
   Keep that temp file for the rest of the cycle — STEP 6 passes it to
   `cycle_log.py finish --edits` to record the submission's size without
   asking you to count anything.
   This is the only path that applies edits: it runs the protected-path guard
   (from the edit list's file paths — no diff parsing needed), then validates
   every edit's `old_string` against the current file content before writing
   anything, so there is no step to skip and no way for an edit to reach the
   tree without passing the guard first. **Exit 2 = the edits touch a protected
   path** (held-out evaluator, gold labels, fixtures, `runs/`, scoring — read
   from `[protected].paths` in the active config) — **REJECT the submission**
   and ask the implementer to resubmit without touching protected files.
   **Exit 1 = an edit failed validation** (`old_string` not found, not unique,
   or a create target that already exists) — show the implementer the exact
   error and ask for a corrected `EDITS` list; do not hand-repair it yourself.
   A submission is atomic: one bad edit means none of them land, so a retry
   resubmits the whole list, not a patch to the failing entry. A retry re-runs
   `mark implement`, which is how a resubmission gets counted. If you abandon
   the cycle instead of retrying, close the record with the reason the control
   gave — `--outcome guard-rejected` for exit 2, `--outcome validation-failed`
   for exit 1 — so a control that fired is visible in the delivery numbers
   rather than disappearing as an unrecorded cycle.
2. **Test path sanity** — Confirm `TEST_FILE:` exists after the edits are applied and is under `tests/`.
3. **Versioning** — A cycle does not change a version by default. Versioning is
   an explicit operator release decision outside this skill.

---

## STEP 5 — Run tests

```bash
uv run pytest tests/ -v
uv run ruff check .
uv run python scripts/cycle_log.py mark test
```

**Both must pass before continuing.** `ruff` is here because CI runs it and this
step is the loop's only chance to catch what CI would: a cycle once landed an
agent-written test with two over-length lines, went green on pytest, passed both
human gates, and turned CI red on push. A gate weaker than the CI it has to
satisfy is not a gate. If tests fail:
1. Read the error output carefully.
2. Fix the issue directly via Edit (do not re-invoke the implementer subagent for small fixes).
3. Re-run `uv run pytest` until all tests pass.

If they cannot be made to pass, close the record with
`--outcome tests-failed` rather than leaving the cycle unrecorded.

---

## STEP 6 — HUMAN APPROVAL: GATE 2 (approve the exact tested tree) ⏸

**The second gate runs after every edit this cycle — code and tests are applied
by now.** Approving
what to build (Gate 1) does not authorize whatever the implementer produced. An
agent can make tests pass by weakening them; a held-out evaluator plus a human
reading the actual diff are what catch that.

1. **Run the app's evaluator, if it declares one, against the pre-cycle baseline STEP 1 captured.**
   ```bash
   EVALUATOR=$(uv run python scripts/flywheel_config.py --get app.evaluator)
   if [ -n "$EVALUATOR" ]; then
     if [ -s .dev_loop_baseline.json ]; then
       eval "$EVALUATOR --baseline .dev_loop_baseline.json" | tee .dev_loop_evaluate.json
     else
       eval "$EVALUATOR" | tee .dev_loop_evaluate.json   # no baseline on record (e.g. first-ever cycle) — score only
     fi
   fi
   uv run python scripts/cycle_log.py mark evaluate
   ```
   `tee` because STEP 6.4 hands both this file and the STEP 1 baseline to
   `cycle_log.py finish`, which derives the metric deltas itself — you never
   transcribe a score.
   Empty `app.evaluator` → no evaluator declared — skip to step 2.
   Capture the machine-readable result. **If it reports `"regression": true`, this is a
   hard failure — treat it exactly like a failing test, not something to note and
   proceed past.** Do not show it to the human as a pass. Go straight to Revert
   (below), or fix the patch and re-run STEP 5 onward. A regression means the loop
   improved the new source by silently breaking one that already worked — for an
   onboarding system that is the worst failure mode there is, so it blocks the gate
   the same way a failing test does. If you revert on this, close the record with
   `--outcome regression-blocked`, not `reverted` — a control firing and a human
   declining are different facts, and collapsing them would overstate the human's
   workload and understate the controls.
2. **Show the human the exact change, and report the metrics honestly.**

   Present, in this order:

   a. The diff hash (`git diff | git hash-object --stdin`), the changed-file list, and
      the diff (or a tight summary if large).

   b. The implementer's `VERIFICATION` table verbatim, and its `LIMITS` block verbatim.
      `LIMITS` is what the change does *not* do, in the implementer's own words. It is
      the line most likely to change a reviewer's decision, so it is never summarised
      away.

   c. **Every metric the evaluator reported — including the ones that did not move.**
      A flat metric beside a rising one is usually the most informative line on the
      page. The rules below are not formatting preferences; each exists because its
      absence produced a wrong decision at this gate before:

      - **Lead with metrics that measure delivered values** — did records actually
        produce usable output. Put metrics that score a *declared* correspondence
        against an answer key after them, labelled as such. Cycle 3 on the
        `fullcontact` split raised `schema_f1` from `0.50` to `0.91` while normalizing
        zero real records for two of its three fields. `schema_f1` scores whether the
        mapping was declared correctly, not whether any value survived it. Presenting
        it as the cycle's headline is how that change got approved.
      - **Never render an unmeasured metric as `0`.** A `null` is "not measured on this
        split" and must be shown as those words, with the reason (e.g. the real
        benchmark pins no value gold). `0.0` means measured and completely wrong. The
        two must never look alike.
      - **Report `integrated_rate` with the ceiling the evaluator computed beside it,
        never bare.** The evaluator emits `integrated_ceiling` and
        `unsatisfiable_required` for every source. Quote both; do not derive, estimate,
        or explain a ceiling yourself. `0.00` reported bare reads as a result, and three
        cycles of `0.00 → 0.00` read as background noise — which is exactly how a real
        signal got ignored once. `0.00, ceiling 0.00 — unsatisfiable: assets, industry,
        revenue` reads as a known bound. The distinction is load-bearing in both
        directions: a `0.00` under a ceiling of `1.00` means the work simply is not done
        yet, and that is a different sentence to write.
        This instruction used to ask you to work the bound out and phrase it by hand. It
        is a number now for the same reason the structured-edit contract exists — a
        model hand-computing something it cannot verify is the failure, not the phrasing.
      - **Do not surface a metric just because the evaluator emits one.** If a number
        does not answer a question the reviewer is actually deciding, it competes for
        attention with the ones that do. Say which question each number answers, and
        drop the ones that answer none.

   d. **Two or three plain sentences on what the result means**, including what it does
      not establish. Not a restatement of the numbers — an interpretation a reviewer can
      disagree with. "Three of four mapped fields now produce values on real records;
      `founded` is declared but yields nothing because the source stores full ISO dates.
      This does not show the mapped targets are the *right* targets — yield says a field
      produces a value, not that the value belongs there."

   Then use AskUserQuestion: "Keep this patch? (Gate 2)" with options Keep / Revert.
3. **On Revert:** restore the pre-cycle tree, report why, and end the cycle cleanly. Because STEP 1 refused to start on a dirty tree, everything uncommitted belongs to this cycle, so `git checkout -- .` followed by `git clean -fd` is safe — gitignored runtime files (e.g. the usage log) are preserved. **On Keep:** proceed.
4. **Close the cycle record**, immediately after the human answers, whichever way
   they answered:
   ```bash
   uv run python scripts/cycle_log.py mark gate2
   uv run python scripts/cycle_log.py finish \
     --outcome kept \
     --edits <the STEP 4 tempfile> \
     --evaluate .dev_loop_evaluate.json \
     --baseline .dev_loop_baseline.json \
     ${FLYWHEEL_EVAL_LOG:+--eval-log "$FLYWHEEL_EVAL_LOG"}
   ```
   Swap `--outcome` for `reverted`, `regression-blocked`, `tests-failed`,
   `guard-rejected`, or `validation-failed` as the cycle actually ended. The
   record is one line under `[app].cycle_log`; `cycle_log.py report` turns the
   accumulated lines into the delivery economics.

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
ADAPTERS_DIR_VAL=$(uv run python scripts/flywheel_config.py --get app.adapters_dir)
[ -n "$ADAPTERS_DIR_VAL" ] && export ADAPTERS_DIR="$ADAPTERS_DIR_VAL"
TARGET_SCHEMA_VAL=$(uv run python scripts/flywheel_config.py --get app.target_schema)
[ -n "$TARGET_SCHEMA_VAL" ] && export TARGET_SCHEMA_PATH="$TARGET_SCHEMA_VAL"
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
- Whether the new operation appears in the simulator
- The cycle's delivery cost, from the record STEP 6 just closed:

```bash
uv run python scripts/cycle_log.py report
```

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
  It holds `Read, Grep, Glob` — no Bash, no Edit, no Write — so returned edits
  are its *only* possible mutation path, and a `PreToolUse` hook declared in
  `implementer.md`'s own frontmatter (`scripts/check_readable.py`, driven by
  `[protected].unreadable`) blocks it from reading fixtures, gold, or `runs/` at
  the tool level, not just by instruction. That hook is scoped to the subagent:
  it binds the implementer and not this orchestrator, which needs `runs/` to
  show receipts at Gate 2. Feature proposal (STEP 2) does not warrant a second subagent:
  the orchestrator already holds the signal report and the app source that
  step needs, and a subagent there would only reformat what it already has —
  its output is a few sentences a human chooses between at Gate 1, which is not
  an isolation boundary worth a round-trip. Everything past the implementer's
  edits is deterministic code (`apply_edits.py`, the evaluator, tests) or a
  human at one of the two gates.
- **Every submission — always, no exceptions — goes through `scripts/apply_edits.py`,
  never a hand-written diff.** That script *is* the guard: it runs the
  protected-path check, then validates every edit's `old_string` against
  current file content, then writes, with no path that skips any of the three.
  The implementer never authors a unified diff — it returns exact-substring
  edits (the same contract as this tool's own Edit/Write tools), which removes
  the actual cause of every malformed-patch failure observed in trial runs: a
  model hand-computing hunk headers and line counts from memory is mechanical
  bookkeeping, exactly what this project avoids pushing onto a model. It also
  narrows the guard itself — a rename, a copy, and a symlink write are all
  diff-format operations with no equivalent in the edit contract, so there is
  nothing left to detect for any of them; the implementer simply cannot express
  those attacks in this format. `.claude/settings.json` also denies
  `Bash(git apply:*)` directly, so there is no shorter path to landing a change
  by hand-crafting a diff instead. **What this is not:** an OS-level boundary.
  The orchestrator holds Edit/Write directly and could bypass this entirely.
  What changed is the failure mode — bypassing the guard now requires
  deliberate evasion, not a forgotten step. See `SECURITY.md`.
- **Two human gates block the loop: STEP 3 (approve the proposal) and STEP 6
  (approve the exact tested tree).** All other steps chain automatically.
- **`check_protected_paths.py` (run inside `apply_edits.py`) refuses to run at
  all if no `flywheel.toml` resolves** — a missing config is not the same as a
  config that declares nothing protected, and blessing a submission because no
  one configured protection would be the guard's own version of the bug it
  exists to prevent. STEP 1 echoes the resolved config up front so this is
  never the operator's first signal that `$FLYWHEEL_CONFIG` was wrong.
- **Continuous mode uses Claude Code's built-in `/loop` runner.** Use `/loop /dev-loop`; stop with Ctrl+C.
- **Do not skip the test step.** A feature is not shipped until `uv run pytest tests/ -v`
  **and** `uv run ruff check .` both pass. Lint is not cosmetic here: it is the
  cheapest check that this cycle's landed code will survive CI, and the loop has
  already shipped a lint-red cycle through both gates once.
- **Do not truncate the usage log** — historical entries are the signal for future cycles.
