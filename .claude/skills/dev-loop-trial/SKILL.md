---
name: dev-loop-trial
description: Measurement mode for the agentic loop — repeats /dev-loop's mechanics with both human gates auto-answered, to measure how reliably the agent converges an empty adapter, not to ship anything. Use for the N-trial runs behind runs/trials/README.md.
allowed-tools: Bash, Read, Edit, Write, Agent
---

# Dev Loop Trial — measuring the agent, not shipping a feature

This is NOT a shortcut for running `/dev-loop` unattended. It is a separate,
labelled mode that exists to answer one question: starting from an empty
adapter, how often does the agent converge it against a held-out oracle, in
how many cycles, and what does it do when it can't?

Every control `/dev-loop` runs still runs here — the protected-path guard on
every patch, `git apply --check`, the full test suite, the evaluator with
`--baseline`, and the `"regression": true` hard stop. The only difference is
that a human does not sit at the two gates: this skill answers them by fixed
rule, and marks every artifact it produces so a trial receipt can never be
mistaken for an approved change.

**This mode is for the real-data test split, run against `adapters_real/`
starting from empty — not against the synthetic dev fixtures, which the
already-committed `runs/forbes/` cycles already show converging.** Real
`forbes` is the right target because the answer is not committed anywhere the
agent (or this skill's author) could have seen it.

---

## Before running any trials

1. `git status --porcelain` must be empty. Trials revert the tree after every
   run; a dirty tree means reverting could destroy real uncommitted work.
2. `FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real.toml` must
   resolve (`uv run python scripts/flywheel_config.py --get app.module`).
3. `engagements/madi_onboarding/adapters_real/forbes.toml` must be at its
   checked-in empty baseline (`source = "forbes"` with no `[fields.*]`
   entries) — every trial starts from the same point, or the convergence rate
   is not comparable across trials.
4. The preconditions in `flywheel.real.toml`'s own header comment
   (`download_data.py`, `csv_to_ingest.py --source forbes`,
   `prepare_real_eval.py`) must already have been run, so
   `engagements/madi_onboarding/data/madi/` exists.
5. **Confirm the trial count and cycle cap with the user before starting.**
   Each trial is a real, subagent-driven loop run — real time and real cost,
   multiplied by N. The plan default is N=10, cap 5 cycles per trial; do not
   silently run a different N.

---

## Per-trial loop

Repeat the following for `trial = 1..N`. Set once per trial, unset after:

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real.toml
export FLYWHEEL_EVAL_LOG="/tmp/dev-loop-trial-${trial}.eval_log.jsonl"
rm -f "$FLYWHEEL_EVAL_LOG"
```

### TRIAL STEP 1 — Baseline (same as /dev-loop STEP 1, minus the human-facing echo)

Confirm the tree is clean, confirm the config resolves, snapshot the baseline
evaluator score:

```bash
[ -z "$(git status --porcelain)" ] || { echo "ABORT: dirty tree before trial $trial"; exit 1; }
EVALUATOR=$(uv run python scripts/flywheel_config.py --get app.evaluator)
rm -f ".dev_loop_trial_baseline.json"
eval "$EVALUATOR" > .dev_loop_trial_baseline.json
```

Start the server against the real config if it is not already up (same
env-export pattern as `/dev-loop` STEP 1, using `TARGET_SCHEMA_PATH` and
`ADAPTERS_DIR` from `[app].target_schema` / `[app].adapters_dir`). Replay a
bounded real-forbes sample (a few hundred records — the evaluator scores all
2000 offline regardless) and run the analyzer, exactly as `/dev-loop` STEP 1
runs the simulator.

### TRIAL STEP 2 — Cycles (cap: 5)

For `cycle = 1..5`, or until convergence:

1. **Propose** — same as `/dev-loop` STEP 2: run `[app].analyzer`, read the
   app source, produce 2-3 grounded proposals.
2. **Auto Gate 1** — take the top-ranked proposal (most affected records in
   the gap report) without asking. Record which one was chosen and why.
3. **Implement** — invoke the `implementer` subagent exactly as `/dev-loop`
   STEP 4 does.
4. **Apply** — `uv run python scripts/apply_patch.py <tempfile>`, the same
   single guarded entry point. A protected-path rejection or a `git apply`
   failure ends the *cycle* (record it as a failure mode) but not necessarily
   the trial — if cycles remain, ask the implementer to resubmit; if not,
   the trial ends non-converged.
5. **Test** — `uv run pytest tests/ -v`. A failure here ends the cycle the
   same way a rejected patch does.
6. **Evaluate** — `eval "$EVALUATOR --baseline .dev_loop_trial_baseline.json"`.
7. **Auto Gate 2** — **Keep** iff tests passed AND `"regression": false`.
   **Revert this cycle's patch** (`git checkout -- .`) otherwise, and stop the
   trial — a trial does not retry a rejected cycle with a different proposal;
   that would no longer be measuring the agent's first attempt at the signal
   it was given.
8. **Check convergence** — the source under test's `schema_f1 == 1.0`
   (the only real-data metric that is meaningful here — `value_recall` and
   `fully_correct_rate` are `null` for the real split; see `evaluate.py`).
   If converged, stop the trial early and record `cycles_used`.
9. Tag everything this trial writes — the CHANGELOG line, any receipt files —
   with `"gates": "auto"` so nothing from a trial can be read as a human
   approval.

### TRIAL STEP 3 — Record and revert

Whatever the outcome (converged, non-converged, or a hard stop), record:

```
trial, converged (bool), cycles_used, final_schema_f1,
regression_blocked (bool), protected_path_rejections (count),
failure_mode (free text, e.g. "git apply failed on cycle 3: <reason>")
```

Then unconditionally restore the pre-trial tree, so the next trial starts
from the same empty `adapters_real/forbes.toml`:

```bash
git checkout -- .
git clean -fd -- engagements/madi_onboarding/adapters_real engagements/madi_onboarding/CHANGELOG.md
```

Count evaluator invocations for this trial from `$FLYWHEEL_EVAL_LOG` (one
line per `evaluate.py` call — see `evaluate.py`'s `FLYWHEEL_EVAL_LOG`
handling) and record it alongside the trial's outcome.

---

## After all N trials

Write `engagements/madi_onboarding/runs/trials/README.md`: convergence rate
(converged / N), the cycles-to-converge distribution, final schema-F1 per
trial, regression-blocked count, protected-path-rejection count, and observed
failure modes in plain language. This file — not any single trial — is the
claim: an *evaluation of* an agentic system, not just a harness for one.

---

## IMPORTANT NOTES

- **Every mechanical control from `/dev-loop` still runs.** This skill changes
  who answers the two gates, not what runs between them.
- **`"gates": "auto"` on every trial artifact** is the only thing that
  distinguishes a trial receipt from a real cycle's. Never omit it.
- **Trials always revert**, Keep or Revert alike — a trial's job is to measure
  convergence, not to leave a converged adapter behind. If a trial should be
  preserved as a real receipt (e.g. to seed `runs/real_forbes/`), that is a
  deliberate, separate, human-run `/dev-loop` cycle, not an artifact of this
  skill.
- **Real forbes, not synthetic.** This skill targets
  `flywheel.real.toml` / `adapters_real/` by design — the synthetic dev
  fixtures already have committed, human-observed converged cycles
  (`runs/forbes/`), which would make a "does the agent converge it" measurement
  meaningless.
