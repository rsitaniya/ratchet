# Security model

**Reader:** a reviewer deciding what the local benchmark harness enforces and what it does not.

## Scope

This is a local, single-operator development loop and benchmark harness. It is not a multi-tenant service and should not be exposed to untrusted callers without separate authentication, authorization, rate limiting, telemetry, and operational controls.

## Enforced workflow controls

| Claim | Mechanism |
|---|---|
| Implementers cannot write directly. | Planner subagents have read-only tool grants and return unified diffs. |
| Protected artifacts cannot be changed by an applied patch. | `scripts/check_protected_paths.py` fails closed on protected, malformed, renamed, copied, or symlink paths before `git apply`. |
| Gold is not a planner input. | Claude Code deny rules block planner `Read` and `Grep` access to fixtures and gold files. |
| A tested patch needs an accountable decision. | Gate 1 approves scope; Gate 2 approves the exact tested patch after tests and evaluator output. |
| A cycle cannot overwrite unrelated local work. | The orchestrator aborts on a dirty working tree. |

## Residual limits

- Claude Code deny rules are not filesystem permissions; changing tool grants changes the boundary.
- A writable adapter or normalizer can still be poor engineering. Aggregate evaluator output and human review limit, but do not eliminate, overfitting risk.
- `X-Usage-Source` and run IDs are caller-set. Assign provenance server-side in an exposed deployment.
- Query parameters are recorded verbatim. Do not treat the local usage log as a secret-safe store.
- Telemetry is append-only and read into memory. Rotate, bound, and harden it before high-volume use.
- `/reconcile` is fixture-scale; production entity resolution needs blocking and resource limits.
- `record_id_hash` in telemetry is a keyed HMAC (`RECORD_ID_HASH_KEY`), not a bare hash, so it resists dictionary/rainbow-table recovery from a guessable id space — but the app falls back to a fixed, non-secret dev key when the env var is unset. Set `RECORD_ID_HASH_KEY` in any real deployment.

## Robustness measures

- Telemetry is fail-open: a logging failure does not turn a served request into a 500.
- Source-system path values are validated and adapter paths must resolve under `adapters/`.
- Batch and reconcile inputs are bounded.
- The simulator rejects a URL join that leaves its configured origin.

Report a security-relevant issue through the repository’s GitHub issues. See [Delivery system architecture](docs/DELIVERY_SYSTEM.md) for the controls in context.
