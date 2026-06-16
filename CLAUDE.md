# Calculator API — Agentic Dev Loop

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
| `app/main.py` | FastAPI app — calculator + usage middleware |
| `usage_log.jsonl` | Runtime product signal (gitignored; auto-created by API traffic) |
| `scripts/simulate.py` | Schema-driven simulator (called by /simulate skill) |
| `tests/` | FastAPI TestClient tests — run with `pytest tests/ -v` |
| `CHANGELOG.md` | Updated each cycle by the orchestrator |
| `.claude/agents/` | Subagent definitions (read-only — orchestrator writes) |
| `.claude/skills/` | Orchestrator skills: simulate, dev-loop |

## Conventions

- **Subagents are read-only planners.** Implementer/docs-updater return standard unified diffs; the dev-loop orchestrator validates with `git apply --check` before applying.
- **Tests use FastAPI TestClient** (in-process). The simulator uses httpx against the live server.
- **Server must be running** before invoking /simulate or /dev-loop.
- **usage_log.jsonl is runtime telemetry.** It is append-only during a run, but gitignored so local simulator traffic does not dirty the submission.
- **Loop closure:** The simulator re-fetches /openapi.json each cycle, so new endpoints are exercised automatically without editing the simulator.
- **Continuous mode:** Use `/loop /dev-loop`; `/dev-loop` itself is one complete cycle.
