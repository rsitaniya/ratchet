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
every submission, the edit-validation check (`old_string` matched exactly once
before anything is written), the full test suite, the evaluator with
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
   resolve (`uv run python scripts/flywheel_config.py --get app.module`), and
   must be set in **Claude Code's own environment**, not just exported inside a
   Bash step. The implementer's read-guard hook inherits Claude Code's
   environment; a Bash `export` does not reach it, and the guard then fails
   closed on every read the implementer makes. Verify with a bare
   `[ -n "$FLYWHEEL_CONFIG" ]` in a Bash call that exports nothing first. If it
   is unset, exit and relaunch as
   `export FLYWHEEL_CONFIG=... && claude`.
3. `engagements/madi_onboarding/adapters_real/forbes.toml` must be at an empty
   baseline (`source = "forbes"` with no `[fields.*]` entries) before the
   first trial starts — every trial starts from the same point, or the
   convergence rate is not comparable across trials. **This is no longer the
   checked-in state**: `/dev-loop` has since landed real mappings into this
   file (see `runs/real_forbes/README.md`), so write the empty stub explicitly
   and confirm with `git diff` that only this file changed before starting.
   Never commit the emptied file — restore it at the end (see "After all N
   trials").
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

Every cycle inside a trial opens and closes a delivery record, exactly as
`/dev-loop` does — `--gates auto` and `--trial` keep trial cost separable from
human-gated cost, so neither contaminates the other's numbers:

```bash
uv run python scripts/cycle_log.py start --cycle "$cycle" --gates auto --trial "$trial"
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
   the gap report) without asking. Record which one was chosen and why, then
   `uv run python scripts/cycle_log.py mark analyze && uv run python scripts/cycle_log.py mark gate1`.
3. **Implement** — invoke the `implementer` subagent exactly as `/dev-loop`
   STEP 4 does. It returns `EDITS` (structured `{file, old_string, new_string}`
   edits, never a hand-written diff — see `implementer.md`), plus `TEST_FILE`,
   `VERIFICATION`, and `LIMITS`, not a patch.
   **Apply `/dev-loop` STEP 4's `VERIFICATION` rule unchanged:** any traced field whose
   result is an error, or a missing `VERIFICATION` on a change that maps data, is a
   rejection and a resubmission — not a note. Auto-answered gates make this the only
   remaining check on a dead mapping, so relaxing it here would let a trial record a
   convergence the human loop would have refused, which makes the trial measure
   nothing. Record such a rejection as a resubmission, exactly like a failed apply.
   Stamp the round-trip when it returns: `uv run python scripts/cycle_log.py mark implement`.
4. **Apply** — `uv run python scripts/apply_edits.py <tempfile>`, the same
   single guarded entry point. Exit 2 (protected-path rejection) or exit 1
   (an edit's `old_string` not found/not unique, or a bad create) both mean
   **nothing was written** — the submission is atomic. **Always ask the
   implementer to resubmit the corrected, complete `EDITS` list; never hand-repair
   an edit yourself.** (An earlier trial run did this inconsistently — repairing
   one malformed diff in place and asking for a full resubmission on another —
   which is exactly the inconsistency this fixed protocol removes.) If cycles
   remain, the resubmission consumes the rest of this cycle's attempt, not a
   new cycle; if none remain, the trial ends non-converged. Record every guard
   rejection and every validation failure as a distinct count in the trial's
   outcome — they measure different things (policy compliance vs. edit
   reliability). `cycle_log.py` records both without a hand count: a resubmission
   is another `mark implement`, and abandoning the cycle takes
   `--outcome guard-rejected` or `--outcome validation-failed`. Stamp a clean
   apply with `uv run python scripts/cycle_log.py mark apply`.
5. **Test** — `uv run pytest tests/ -v` and `uv run ruff check .` (same pair as
   `/dev-loop` STEP 5 and as CI — a trial that ignores lint would measure
   convergence the real loop would not accept), then
   `uv run python scripts/cycle_log.py mark test`. A failure here ends the cycle
   the same way a rejected/invalid submission does (`--outcome tests-failed`).
6. **Evaluate** — `eval "$EVALUATOR --baseline .dev_loop_trial_baseline.json" | tee .dev_loop_trial_evaluate.json`,
   then `uv run python scripts/cycle_log.py mark evaluate`.
7. **Auto Gate 2** — **Keep** iff tests passed AND `"regression": false`.
   **Revert this cycle's patch** (`git checkout -- .`) otherwise, and stop the
   trial — a trial does not retry a rejected cycle with a different proposal;
   that would no longer be measuring the agent's first attempt at the signal
   it was given.
8. **Check convergence** — the source under test's `schema_f1 == 1.0`
   (the only real-data metric that is meaningful here — `value_recall` and
   `fully_correct_rate` are `null` for the real split; see `evaluate.py`).
   If converged, stop the trial early and record `cycles_used`.
9. Tag every receipt or trial artifact this run writes with `"gates": "auto"`
   so nothing from a trial can be read as a human
   approval. `cycle_log.py` already stamps that field on its own record; close
   the cycle with the outcome the trial actually reached:
   ```bash
   uv run python scripts/cycle_log.py mark gate2
   uv run python scripts/cycle_log.py finish --outcome kept \
     --edits <this cycle's edits tempfile> \
     --evaluate .dev_loop_trial_evaluate.json \
     --baseline .dev_loop_trial_baseline.json \
     --eval-log "$FLYWHEEL_EVAL_LOG"
   ```
   An auto-gated cycle still records `gate1`/`gate2` marks, and their durations
   are near zero by construction. That is the point: it is what a human-gated
   cycle's numbers get compared against.

### TRIAL STEP 3 — Record and revert

Whatever the outcome (converged, non-converged, or a hard stop), record:

```
trial, converged (bool), cycles_used, final_schema_f1,
regression_blocked (bool), protected_path_rejections (count),
edit_validation_failures (count — old_string not found/not unique, bad create),
failure_mode (free text, e.g. "cycle 3: old_string not unique in forbes.toml, resubmitted, then converged")
```

`protected_path_rejections` and `edit_validation_failures` are separate counts on
purpose — a protected-path rejection is a policy-compliance signal (did the
implementer try to touch something it shouldn't), an edit-validation failure is
a mechanical-reliability signal (did its edit actually apply). Conflating them
would hide which one an anomalous trial is actually telling you about.

Then unconditionally restore the pre-trial tree. **`git checkout -- .` alone is
no longer enough**: HEAD's `adapters_real/forbes.toml` now carries the real
mappings `/dev-loop` landed, so checking out HEAD would start the next trial
from that non-empty state instead of empty. Re-apply the empty stub from
precondition 3 after the checkout, every time:

```bash
git checkout -- .
git clean -fd -- engagements/madi_onboarding/adapters_real tests/
# HEAD's forbes.toml is no longer empty — re-write the stub so the next trial
# still starts from the same empty point precondition 3 established.
cat > engagements/madi_onboarding/adapters_real/forbes.toml <<'EOF'
source = "forbes"

[fields]
EOF
```

Evaluator invocations, cycle durations, resubmissions, and control stops are
already in the delivery record `cycle_log.py finish` wrote — do not recount them
by hand. Read them back with:

```bash
uv run python scripts/cycle_log.py report
```

---

## After all N trials

**Restore the real committed mappings first.** The per-trial reset above leaves
the empty stub in the working tree, not HEAD's actual `adapters_real/forbes.toml`
(which carries the mappings landed by `/dev-loop` — see
`runs/real_forbes/README.md`). Before doing anything else:

```bash
git checkout -- engagements/madi_onboarding/adapters_real/forbes.toml
git status --porcelain   # must be empty again
```

Write `engagements/madi_onboarding/runs/trials/README.md`: convergence rate
(converged / N), the cycles-to-converge distribution, final schema-F1 per
trial, regression-blocked count, protected-path-rejection count,
edit-validation-failure count, and observed failure modes in plain language.
This file — not any single trial — is the claim: an *evaluation of* an
agentic system, not just a harness for one.

---

## IMPORTANT NOTES

- **Every mechanical control from `/dev-loop` still runs.** This skill changes
  who answers the two gates, not what runs between them. The implementer's read
  boundary (`scripts/check_readable.py`, hooked into the implementer subagent
  from its own frontmatter) is one of them: a trial can never begin by reading a
  previous trial's converged mapping out of `runs/`.
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
