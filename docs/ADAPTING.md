# Adapt the loop to another FastAPI API

**Reader:** an engineer applying the generic delivery loop to a new local FastAPI service.

An engagement gives the loop four things: traffic, a domain signal, an evaluator when correctness needs one, and a narrow change surface. The loop supplies simulation, edit validation, approval gates, and test execution.

## Preconditions

- The service exposes OpenAPI at `/openapi.json`.
- Product requests are recorded as JSONL, including unknown-path `404`s.
- An operator can run the service locally and approve scope and tested changes.
- The engagement has a domain analyzer. There is no generic fallback.

## Minimal configuration

```toml
[app]
module = "myservice.api:app"
base_url = "http://localhost:8000"
analyzer = "uv run python myservice/analyze.py"
```

Set `FLYWHEEL_CONFIG=path/to/flywheel.toml` to select a non-root configuration. Paths such as `usage_log` and a replay file resolve relative to that file. A missing configured file is an error. Fix the path or unset `FLYWHEEL_CONFIG`.

## Required telemetry

The analyzer needs enough context to distinguish a transport event from a product gap:

```json
{"timestamp":"...","event":"http","path":"/refund","method":"POST","status_code":404,"latency_ms":0.4,"error_type":null,"source":"simulator","run_id":null}
```

Adapt the `usage_logger` middleware in `engagements/madi_onboarding/app/main.py`. Keep unknown product paths. A `404` can be useful evidence of failed intent.

## Add the controls your domain needs

| Need | Configuration or component | What to verify |
|---|---|---|
| Reproducible traffic | `traffic.replay_file` or `simulate.py --replay` | A clean run creates the expected telemetry. |
| Domain correctness beyond HTTP | `[app].evaluator` | A known-wrong change lowers its score. |
| Regression detection | Evaluator support for `--baseline FILE` | A known regression is rejected. |
| Protected evaluator assets | `[protected].paths` | A returned structured edit targeting a protected path is rejected. |
| Separate evaluation distribution | A second config, fixtures, oracle, and write surface | The development adapter cannot silently overwrite the test surface. |

An evaluator must emit JSON. It should accept `--baseline FILE` when regression matters. Keep its scorer, labels, fixtures, and engines outside the implementer’s readable and writable surface. This is a local workflow boundary. It does not replace production security controls.

## Acceptance checks

1. Start the API with the active configuration.
2. Run `uv run python scripts/simulate.py` with no hand-written endpoint list.
3. Confirm the usage log contains endpoint traffic and unknown-path `404`s.
4. Add a schema-visible endpoint and repeat. The simulator should exercise it without code changes.
5. Run the analyzer and confirm it produces a ranked, actionable signal.
6. If an evaluator exists, prove a known-wrong change lowers its score and a protected-path edit is rejected.
7. Run one cycle with a clean worktree and confirm that the final decision is an explicit Gate 2 approval.

The [delivery-system architecture](DELIVERY_SYSTEM.md) explains the generic contracts. The [security model](../SECURITY.md) states the limits of the local controls.
