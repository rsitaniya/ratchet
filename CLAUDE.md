# Calculator API — Agentic Dev Loop

## Quick start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Start the API (--reload picks up new routes automatically)
uvicorn app.main:app --reload

# 3. Run the simulator (in a second terminal or new Claude Code session)
/simulate

# 4. Run the full agentic development cycle
/dev-loop
```

## Key files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI app — calculator + usage middleware |
| `usage_log.jsonl` | Append-only product signal (never truncate between cycles) |
| `scripts/simulate.py` | Schema-driven simulator (called by /simulate skill) |
| `tests/` | FastAPI TestClient tests — run with `pytest tests/ -v` |
| `CHANGELOG.md` | Updated each cycle by the orchestrator |
| `.claude/agents/` | Subagent definitions (read-only — orchestrator writes) |
| `.claude/skills/` | Orchestrator skills: simulate, dev-loop |

## Conventions

- **Subagents are read-only planners.** They return structured text; the dev-loop orchestrator applies all file writes (Edit/Write/Bash).
- **Tests use FastAPI TestClient** (in-process). The simulator uses httpx against the live server.
- **Server must be running** before invoking /simulate or /dev-loop.
- **usage_log.jsonl is append-only.** Older entries are the signal; do not delete them between cycles.
- **Loop closure:** The simulator re-fetches /openapi.json each cycle, so new endpoints are exercised automatically without editing the simulator.
