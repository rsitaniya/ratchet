# Local runbook

**Reader:** a practitioner running the bundled example or the reference engagement locally.

## Prerequisites

- Python 3.11–3.13
- Two terminals
- Claude Code only if you want to run `/simulate` or `/dev-loop`

```bash
pip install -e ".[dev]"
pytest tests/ -q
ruff check .
```

Expected result: the test suite passes and Ruff reports no findings.

## Example API: create signal

Terminal 1:

```bash
uvicorn app.main:app --reload
```

Terminal 2:

```bash
python scripts/simulate.py http://localhost:8000 30
python scripts/analyze_usage.py usage_log.jsonl
```

The simulator reads `/openapi.json`, exercises the available endpoints, and writes only product-endpoint telemetry. Stop the server with `Ctrl+C`.

## Reference engagement: replay partner onboarding

Terminal 1:

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
export USAGE_LOG_PATH=$(python scripts/flywheel_config.py --get app.usage_log)
uvicorn "$(python scripts/flywheel_config.py --get app.module)" --port 8000
```

Terminal 2:

```bash
python engagements/madi_onboarding/to_replay.py --source forbes
python scripts/simulate.py --run-id local-baseline
python engagements/madi_onboarding/analyze_integration.py "$USAGE_LOG_PATH" --source forbes --run-id local-baseline
python engagements/madi_onboarding/evaluate.py
```

The shipped `forbes` adapter is intentionally empty: this command reports the baseline. The documented successful states live in [run receipts](engagements/madi_onboarding/runs/README.md); do not replace the baseline adapter unless you intend to reproduce a cycle.

## Run a reviewed agent cycle

With Claude Code open in the repository:

```text
/dev-loop
```

The loop refuses a dirty working tree, asks for scope approval, validates the returned diff, runs tests and the configured evaluator, then asks whether to retain the exact tested patch. `/loop /dev-loop` repeats this workflow; it does not remove either approval gate.

## Common failures

| Symptom | Check |
|---|---|
| `ModuleNotFoundError: engagements` | Reinstall with `pip install -e ".[dev]"`; do not use the runtime-only dependency path. |
| Simulator cannot connect | Confirm the server, port, and `base_url` in the active configuration. |
| No integration telemetry | Confirm `USAGE_LOG_PATH` is exported before starting the engagement API. |
| Evaluator result differs from a receipt | Confirm which adapter snapshot is installed and use the receipt’s prior evaluator output as `--baseline`. |

For the configuration interface, see [docs/ADAPTING.md](docs/ADAPTING.md).
