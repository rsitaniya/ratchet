# dev-flywheel — Agentic Dev Loop

The bundled calculator in `app/` is the **example app**, not the point. The loop is
the project. Domain knowledge lives in `flywheel.toml`, `edge_cases.json`, and
per-engagement packages under `engagements/` only — see `docs/ADAPTING.md`.

The reference engagement, `engagements/madi_onboarding/`, points the same generic
loop at a partner-data onboarding API benchmarked on MaDI-Bench, with a **held-out
evaluator** the loop is forbidden to edit. It selects itself purely via
`FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml`.

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the API (--reload picks up new routes automatically)
uvicorn app.main:app --reload

# 3. Run the simulator (in a second terminal or new Claude Code session)
/simulate

# 4. Run one full agentic development cycle
/dev-loop

# Bonus: run cycles continuously with Claude Code's built-in loop runner
/loop /dev-loop
```

## Key files

| File | Purpose |
|------|---------|
| `flywheel.toml` | **The only seam between the loop and a specific API** — app module, version files, signal params |
| `edge_cases.json` | Correlated domain edge cases for the simulator (optional; grown by the loop each cycle) |
| `app/main.py` | Example FastAPI app — calculator + usage middleware |
| `usage_log.jsonl` | Runtime product signal (gitignored; auto-created by API traffic) |
| `scripts/simulate.py` | Schema-driven simulator (called by /simulate skill) |
| `scripts/analyze_usage.py` | Turns the raw log into the signal report the feature-suggester reads |
| `scripts/flywheel_config.py` | Loads the active `flywheel.toml` (via `FLYWHEEL_CONFIG`); `--get KEY` accessor for shell steps |
| `scripts/check_protected_paths.py` | Rejects any patch touching held-out evaluators/gold/fixtures (`[protected].paths`) |
| `engagements/madi_onboarding/` | Reference engagement: partner-data onboarding, ingest app, adapters, protected evaluator, case study |
| `tests/` | FastAPI TestClient tests — run with `pytest tests/ -v` |
| `CHANGELOG.md` | Updated each cycle by the orchestrator |
| `docs/ADAPTING.md` | How to point the loop at your own API |
| `.claude/agents/` | Subagent definitions (read-only — orchestrator writes) |
| `.claude/skills/` | Orchestrator skills: simulate, dev-loop |

## Conventions

- **Subagents are read-only planners.** Implementer/docs-updater return standard unified diffs; the dev-loop orchestrator validates with `git apply --check` before applying.
- **Tests use FastAPI TestClient** (in-process). The simulator uses httpx against the live server.
- **Server must be running** before invoking /simulate or /dev-loop.
- **usage_log.jsonl is runtime telemetry.** It is append-only during a run, but gitignored so local simulator traffic does not dirty the submission.
- **Loop closure:** The simulator re-fetches /openapi.json each cycle, so new endpoints are exercised automatically without editing the simulator.
- **Continuous mode:** Use `/loop /dev-loop`; `/dev-loop` itself is one complete cycle.
- **No domain knowledge in the loop.** `scripts/` and `.claude/` must stay generic. Anything app-specific belongs in `flywheel.toml`, `edge_cases.json`, or an `engagements/<name>/` package. All degrade gracefully when absent.
- **Two human gates + a protected evaluator.** The loop blocks at Gate 1 (approve the proposal) and Gate 2 (approve the exact tested patch after the app's `[app].evaluator` runs). The implementer may never edit paths in `[protected].paths` (held-out evaluator, gold, fixtures) — `check_protected_paths.py` enforces this before `git apply`.
- **Adapters are data.** An engagement grows mostly by adding declarative config the app reads (e.g. onboarding adapters), not agent-written code; new code is reserved for genuinely new behavior and is covered by tests + the evaluator.
