# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

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
