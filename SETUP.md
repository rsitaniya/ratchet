# Run the reference engagement

**Reader:** an engineer who wants to reproduce the synthetic onboarding baseline, inspect its signal, or run a reviewed change cycle.

The shipped `forbes` adapter is intentionally empty. This run establishes the same zero-state baseline used by the recorded onboarding receipts. It does not replay a pre-solved result.

## Prerequisites

- Python 3.11–3.13
- [uv](https://pypi.org/project/uv/)
- Two terminals
- Claude Code only for `/simulate`, `/dev-loop`, or `/dev-loop-trial`

```bash
uv sync --all-extras --locked
uv run pytest tests/ -q
uv run ruff check .
```

Expected result: tests pass and Ruff reports no findings.

## Replay the onboarding baseline

In terminal 1, select the synthetic development engagement and start the API:

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
export USAGE_LOG_PATH=$(uv run python scripts/flywheel_config.py --get app.usage_log)
uv run uvicorn "$(uv run python scripts/flywheel_config.py --get app.module)" --port 8000
```

In terminal 2, create replay traffic, run it, then inspect the ranked gaps and evaluator result:

```bash
uv run python engagements/madi_onboarding/to_replay.py --source forbes
uv run python scripts/simulate.py --run-id local-baseline
uv run python engagements/madi_onboarding/analyze_integration.py "$USAGE_LOG_PATH" --source forbes --run-id local-baseline
uv run python engagements/madi_onboarding/evaluate.py
```

This proves that the local API, replay, telemetry, analyzer, and evaluator are connected. It reports the empty-adapter baseline. Compare it with the [onboarding receipts](engagements/madi_onboarding/runs/MADI_EXAMPLE.md#forbes-onboarding-schema-matching--value-normalization) for the two recorded changes.

## Run one reviewed change cycle

Export the engagement configuration **before** launching Claude Code, then run
the loop:

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
claude
```

```text
/dev-loop
```

The order matters. The implementer's read guard runs as a `PreToolUse` hook, and
a hook inherits Claude Code's own environment — exporting the variable inside a
Bash step later does not reach it. Launch without it and the guard fails closed
on every read the implementer makes, including the app source it needs.
`/dev-loop` STEP 1 refuses to start in that state rather than letting the cycle
fail confusingly further in.

The loop rejects a dirty worktree, presents a scoped proposal, validates the returned structured edits, runs tests and the configured evaluator, then asks whether to retain the exact tested result. `/loop /dev-loop` repeats this workflow. It does not remove either approval gate.

Each cycle also records what it cost. Read the accumulated delivery numbers with:

```bash
uv run python scripts/cycle_log.py report
```

## Inspect the real-data trial setup

The separate MaDI-Bench configuration is for measurement, not ordinary local development:

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real.toml
uv run python engagements/madi_onboarding/download_data.py
uv run python engagements/madi_onboarding/csv_to_ingest.py --source forbes
uv run python engagements/madi_onboarding/prepare_real_eval.py
```

Read the [real-data baseline](engagements/madi_onboarding/runs/real_forbes/README.md) and [convergence-trial report](engagements/madi_onboarding/runs/trials/README.md) before running `/dev-loop-trial`. The trial auto-answers both gates and reverts its work. It is a measurement harness, not a path for landing changes.

## Common failures

| Symptom | Check |
|---|---|
| `ModuleNotFoundError: engagements` | Run `uv sync --all-extras --locked` from the repository root. |
| Simulator cannot connect | Confirm the API is running, its port matches the active configuration, and the configured `base_url` is correct. |
| No integration telemetry | Export `USAGE_LOG_PATH` before starting the API. |
| Evaluator result differs from a receipt | Check which adapter or rule snapshot is installed and which prior evaluator output was used as `--baseline`. |
| Protected-path rejection | Confirm the edit targets an adapter or rule, not fixtures, gold, engines, evaluator, or `runs/`. |
| Implementer reports a denied read | Expected for gold, fixtures, and `runs/`. If an ordinary source file is denied, check `[protected].unreadable` in the active configuration. |
| Every implementer read is denied, including app source | `FLYWHEEL_CONFIG` was not set in Claude Code's environment at launch. The read guard fails closed rather than guessing an engagement. Exit, export it, relaunch. |
| `no cycle in progress` | `cycle_log.py mark` ran before `cycle_log.py start`. Start a cycle, or ignore it if you are not measuring. |

For another API, use the [adaptation guide](docs/ADAPTING.md).
