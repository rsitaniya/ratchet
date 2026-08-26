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

[signals]
numeric_params = ["amount"]
zero_value_params = ["amount"]
```

Select a non-root configuration with `FLYWHEEL_CONFIG=path/to/flywheel.toml`. Paths such as `usage_log`, `edge_cases`, and a replay file resolve relative to that configuration.

## Required telemetry shape

```json
{"timestamp":"...","path":"/refund","method":"POST","inputs":{},"status_code":404,"latency_ms":0.4,"error_type":null,"source":"simulator"}
```

Copy and adapt the middleware in `app/main.py`. Do not exclude unknown product paths: a 404 is a useful failed-intent signal, not an infrastructure endpoint.

## Optional domain controls

| Need | Configuration / component |
|---|---|
| Correlated inputs | `edge_cases.json` |
| Reproducible traffic | `traffic.replay_file` or `simulate.py --replay` |
| Domain correctness beyond HTTP | `[app].evaluator` |
| Evaluator, gold, fixture, or scoring protection | `[protected].paths` |
| Richer signal than HTTP rates | Engagement-specific analyzer |

An evaluator must emit JSON and accept `--baseline FILE` when regression matters. The implementer must not be able to modify its scorer, labels, or fixtures. This is a workflow boundary, not a production security boundary; see [SECURITY.md](../SECURITY.md).

## Acceptance check

1. Start the API with the active configuration.
2. Run `python scripts/simulate.py` with no hand-written endpoint list.
3. Confirm the usage log contains new endpoint traffic and unknown-path 404s.
4. Add a schema-visible endpoint and repeat; the simulator must exercise it without code changes.
5. If using an evaluator, prove a known-wrong change lowers its score and a protected-path edit is rejected.

Architecture and non-goals: [Delivery system architecture](DELIVERY_SYSTEM.md).
