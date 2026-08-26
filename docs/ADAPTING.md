# Adapt the loop to another FastAPI API

**Reader:** an engineer integrating the generic loop with a new local FastAPI service.

## Preconditions

- The service exposes OpenAPI at `/openapi.json`.
- Product requests are recorded as JSONL, including 404s.
- The operator can run the service locally and approve every proposed change.

## Configuration contract

```toml
[app]
module = "myservice.api:app"
base_url = "http://localhost:8000"
version_files = ["myservice/api.py", "pyproject.toml", "CHANGELOG.md"]
# Required: the loop has no generic fallback analyzer. Point it at a script that
# turns the usage log into a ranked signal report (see analyze_integration.py
# for the shape /dev-loop STEP 2 expects).
analyzer = "python myservice/analyze.py"
```

Select a non-root configuration with `FLYWHEEL_CONFIG=path/to/flywheel.toml`. Paths such as `usage_log` and a replay file resolve relative to that configuration. `FLYWHEEL_CONFIG` pointing at a file that does not exist is an error, not a silent fallback — fix the path or unset it.

## Required telemetry shape

```json
{"timestamp":"...","event":"http","path":"/refund","method":"POST","status_code":404,"latency_ms":0.4,"error_type":null,"source":"simulator","run_id":null}
```

Copy and adapt the `usage_logger` middleware in `engagements/madi_onboarding/app/main.py`. Do not exclude unknown product paths: a 404 is a useful failed-intent signal, not an infrastructure endpoint.

## Optional domain controls

| Need | Configuration / component |
|---|---|
| Reproducible traffic | `traffic.replay_file` or `simulate.py --replay` |
| Domain correctness beyond HTTP | `[app].evaluator` |
| Evaluator, gold, fixture, or scoring protection | `[protected].paths` |

An evaluator must emit JSON and accept `--baseline FILE` when regression matters. The implementer must not be able to modify its scorer, labels, or fixtures. This is a workflow boundary, not a production security boundary; see [SECURITY.md](../SECURITY.md).

## Acceptance check

1. Start the API with the active configuration.
2. Run `uv run python scripts/simulate.py` with no hand-written endpoint list.
3. Confirm the usage log contains new endpoint traffic and unknown-path 404s.
4. Add a schema-visible endpoint and repeat; the simulator must exercise it without code changes.
5. If using an evaluator, prove a known-wrong change lowers its score and a protected-path edit is rejected.

Architecture and non-goals: [Delivery system architecture](DELIVERY_SYSTEM.md).
