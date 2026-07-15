# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

## [0.5.0] - 2026-06-16

### Added
- Added safe_divide operation to /calculate and /calculate/batch endpoints that returns null result instead of HTTP 400 when b=0, enabling graceful null-handling in client code.

## [0.4.0] - 2026-06-16

### Added
- Added POST /calculate/batch endpoint that accepts a JSON array of {op, a, b} objects and returns per-item results in a single round-trip, isolating per-item errors (DivisionByZero, Overflow, NonFiniteInput) without aborting the batch.

### Changed
- Usage collection is now **endpoint-generic**: the middleware records every product endpoint (everything outside `SKIP_USAGE_PATHS`), not just `/calculate`. Records gain `path` and `method` fields and `inputs` now captures all query params. This closes the feedback loop for any feature shape — new endpoints' traffic becomes signal automatically.
- `analyze_usage.py` keys its breakdown by `op` for `/calculate` and by `path` for other endpoints, and adds a **Requested-but-missing endpoints (HTTP 404)** section so unmet demand surfaces as a build signal.
- Subagent handoffs now use standard unified diffs validated with `git apply --check` before application, replacing prose insertion points and ad hoc find/replace patching.
- The automated bonus now uses Claude Code's built-in `/loop /dev-loop` runtime runner; `/dev-loop` itself remains one complete, test-gated cycle.

### Added
- `tests/test_usage_logging.py` — functional TestClient tests asserting that product endpoints are recorded, unknown paths are captured as 404 signal, and infra endpoints (`/health`) are excluded.

### Fixed
- `usage_log.jsonl` is now gitignored and untracked (runtime artifact), matching its description in SETUP.md.

## [0.3.0] - 2026-06-16

### Added
- `abs` operation on `/calculate` computing `|a - b|` (absolute difference) — shipped via agentic dev-loop cycle 2 (suggested from 82 calls with negative a, 76 with negative b)

## [0.2.0] - 2026-06-16

### Added
- `mod` operation on `/calculate` computing `a % b` with HTTP 400 DivisionByZero guard when `b=0` — shipped via agentic dev-loop cycle 1 (suggested by feature-suggester from 2/129 calls returning HTTP 422 on op=modulo)
- Non-finite input rejection: `nan`/`inf`/`-inf` operands return HTTP 422 `NonFiniteInput`; overflowing results return HTTP 400 `Overflow`
- `source` field on usage records (from `X-Usage-Source` header) to separate simulator traffic from organic traffic
- `scripts/analyze_usage.py` — converts the raw log into a per-operation signal report consumed by the feature-suggester

### Changed
- feature-suggester now reads the analyze_usage.py report and skips already-implemented features (no more chasing stale signals)
- `/dev-loop` runs continuously (bonus): loops back automatically after each cycle; human approval is the only blocking step

### Fixed
- Tests no longer pollute `usage_log.jsonl` (`tests/conftest.py` redirects the log during the test session)
- `pytest tests/ -v` works via `pyproject.toml` `pythonpath` config
- Simulator fails loudly if `/openapi.json` has no `op` enum instead of silently using a hardcoded op list

## [0.1.0] - 2026-06-16

### Added
- Initial FastAPI calculator with add, subtract, multiply, divide operations
- Usage middleware recording timestamp, operation, inputs, status_code, latency_ms, error_type to usage_log.jsonl
- Schema-driven simulator skill (/simulate) that exercises all endpoints from /openapi.json
- Agentic dev-loop orchestrator (/dev-loop) with human approval gate
- feature-suggester, implementer, docs-updater subagents
