# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- Add `mod` operation to `/calculate` endpoint computing `a % b` with HTTP 400 DivisionByZero guard when `b=0` — shipped via agentic dev-loop cycle 1 (suggested by feature-suggester from 2/129 calls returning HTTP 422 on op=modulo)

## [0.1.0] - 2026-06-16

### Added
- Initial FastAPI calculator with add, subtract, multiply, divide operations
- Usage middleware recording timestamp, operation, inputs, status_code, latency_ms, error_type to usage_log.jsonl
- Schema-driven simulator skill (/simulate) that exercises all endpoints from /openapi.json
- Agentic dev-loop orchestrator (/dev-loop) with human approval gate
- feature-suggester, implementer, docs-updater subagents
