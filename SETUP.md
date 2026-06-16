# SETUP.md — Agentic Development Loop

A self-feeding, data-driven feature-shipping loop built on FastAPI + Claude Code.
The loop generates usage signal, proposes features from data, gets human approval,
implements + tests, updates docs, then re-exercises the new endpoint automatically.

---

## Prerequisites

- Python 3.11+
- Claude Code CLI (`claude`) installed and authenticated
- Two terminal windows (one for the API server, one for Claude Code)

```bash
pip install -r requirements.txt
```

---

## How to run the loop end-to-end

### Terminal 1 — Start the API

```bash
uvicorn app.main:app --reload
```

`--reload` is required so new routes added by the implementer are picked up without
a manual restart. (`watchfiles` in `requirements.txt` powers this.)

The API is now live at http://localhost:8000. Docs at http://localhost:8000/docs.

### Terminal 2 — Claude Code

```bash
claude   # opens Claude Code in the project directory
```

**Step 1 — Populate usage data:**
```
/simulate
```

**Step 2 — Run the full agentic cycle:**
```
/dev-loop
```

The loop will:
1. Simulate API traffic → populates `usage_log.jsonl`
2. Invoke the feature-suggester → returns 2-3 proposals grounded in the data
3. **Stop and ask you to pick a feature** ← only blocking step
4. Invoke the implementer → returns structured code
5. Orchestrator applies the writes, runs `pytest`, confirms tests pass
6. Restart server to reload new routes
7. Invoke docs-updater → ensures new route has complete OpenAPI metadata
8. Re-run simulator to confirm new endpoint appears in schema and is exercised

---

## What each subagent does and how they hand off

```
/dev-loop (orchestrator, parent skill)
    │
    ├─ [Bash] python scripts/simulate.py → usage_log.jsonl populated
    │
    ├─ [Agent] feature-suggester ──────────────────────────────────────────┐
    │       reads: usage_log.jsonl                                          │
    │       returns: PROPOSALS block (2-3 options with signal + complexity) │
    │   ◄───────────────────────────────────────────────────────────────────┘
    │
    ├─ [AskUserQuestion] ⏸ HUMAN PICKS ONE FEATURE
    │
    ├─ [Agent] implementer ─────────────────────────────────────────────────┐
    │       reads: app/main.py (for style/context)                          │
    │       returns: FILE/CODE/TEST_FILE/TEST_CODE/CHANGELOG structured text │
    │   ◄───────────────────────────────────────────────────────────────────┘
    │
    ├─ [Edit/Write] Orchestrator applies the code + test + changelog writes
    ├─ [Bash] pytest tests/ -v  ← must pass before continuing
    ├─ [Bash] restart uvicorn
    │
    ├─ [Agent] docs-updater ────────────────────────────────────────────────┐
    │       reads: app/main.py                                              │
    │       returns: FIND/REPLACE patches for OpenAPI metadata              │
    │   ◄───────────────────────────────────────────────────────────────────┘
    │
    ├─ [Edit] Orchestrator applies metadata patches
    └─ [Bash] simulator re-run → confirms new endpoint in /openapi.json
```

**Key design: subagents are read-only planners.** They return structured text;
the orchestrator applies every file write. This means:
- No permission prompts inside subagents
- Single point of control for all mutations
- Clean, auditable handoffs — the structured output format is the contract

---

## Where the human-approval step lives

In **`/dev-loop`** (the parent orchestrator skill), not in any subagent.

Specifically, after the feature-suggester returns its PROPOSALS block,
the orchestrator calls `AskUserQuestion` with the proposals as options.
This is the only `AskUserQuestion` call in the entire system.
Everything before and after it chains automatically.

This placement is deliberate: subagents in Claude Code cannot block for
user input (they run headlessly). The approval gate must be in the parent
skill where the interactive session lives.

---

## How the usage-collection mechanism works and why it's designed this way

### Mechanism

A FastAPI middleware (`@app.middleware("http")` in `app/main.py`) intercepts every
request to `/calculate` and appends a JSON record to `usage_log.jsonl`:

```json
{
  "timestamp": "2026-06-16T10:23:45.123Z",
  "operation": "divide",
  "inputs": {"a": "10", "b": "0"},
  "status_code": 400,
  "latency_ms": 1.23,
  "error_type": "DivisionByZero"
}
```

The file is append-only. Historical entries accumulate across cycles.

### Why middleware, not application-level logging

Middleware fires unconditionally on every request, including requests that
raise validation errors (422) before the route handler runs. This means
"attempted but unsupported" operations (like `op=modulo` before modulo exists)
appear as 422 errors in the log — which is exactly the signal that tells us
to add that operation.

Application-level logging (inside the route handler) would miss those.

### Why jsonl, not a database

One JSON object per line means:
- Zero setup — no DB, no schema migration
- `wc -l usage_log.jsonl` gives total call count instantly
- `grep '"operation":"divide"' usage_log.jsonl | wc -l` gives per-op count
- The feature-suggester reads it with two lines of Python
- Append-only = safe for concurrent single-worker writes

### Why this is product signal, not just a log

Each record contains `error_type` (machine-readable), not just `status_code`.
The feature-suggester looks for patterns like:

- `error_type: DivisionByZero` in 12% of divide calls → add safe-divide or modulo
- `status_code: 422` on unknown `op` values → add the missing operation
- High `latency_ms` on any operation → performance signal
- Zero-value inputs concentrated on one operation → add guard/edge-case handling

This mirrors how a real PM would use event-stream data: error rates, input
distributions, and failed-intent signals (422s on unknown ops) all point at
concrete product gaps.

---

## Which plugins/skills were used and why

| Component | What it is | Why used |
|-----------|-----------|---------|
| `.claude/skills/simulate/SKILL.md` | Native Claude Code skill | Single-command invocation (`/simulate`), no framework overhead |
| `.claude/skills/dev-loop/SKILL.md` | Native Claude Code skill | Orchestrates the full cycle; has access to `AskUserQuestion` for the approval gate |
| `.claude/agents/feature-suggester.md` | Native Claude Code subagent | Scoped read-only tools; clear system prompt; invoked via `Agent` tool from orchestrator |
| `.claude/agents/implementer.md` | Native Claude Code subagent | Read-only — returns structured text the orchestrator applies |
| `.claude/agents/docs-updater.md` | Native Claude Code subagent | Read-only — returns FIND/REPLACE patches for metadata |
| FastAPI `TestClient` | FastAPI built-in | In-process tests; no live server needed; idiomatic for FastAPI projects |
| `scripts/simulate.py` | Plain Python + httpx | Generic schema-driven simulator; zero dependency on simulator knowing the API |

**Why native skills over a marketplace framework:**
The `.claude/skills/<name>/SKILL.md` + `.claude/agents/<name>.md` convention
is Claude Code's built-in orchestration layer. It requires no installation,
no API keys beyond what Claude Code already has, and is self-documenting
(the SKILL.md is both the implementation and the readme). A heavy framework
(LangGraph, CrewAI, etc.) would add complexity without adding capability for
a loop this size.

---

## How to adapt this setup to a different API

The only components that are calculator-specific:

1. **`app/main.py`** — replace entirely with your API
2. **`DOMAIN_EDGE_CASES` dict in `scripts/simulate.py`** — update edge cases for your domain (e.g., for a payments API: `{"amount": 0}`, `{"currency": "INVALID"}`, `{"amount": -1}`)
3. **The `op` param extraction in `extract_operations()`** — update to match your API's enum or parameter name

Everything else is generic:

- The middleware pattern works for any FastAPI app — just change the path filter from `/calculate` to your endpoints
- The feature-suggester prompt works for any `usage_log.jsonl` with the same schema
- The implementer and docs-updater prompts are FastAPI-specific but broadly applicable to any Python/FastAPI service
- The dev-loop orchestrator is fully generic — it reads whatever the subagents return
- The simulator's schema-parsing logic works for any OpenAPI 3.x spec

**To target a non-FastAPI API:** replace the simulator with a script that fetches
your API's documentation (Swagger, Postman collection, or a markdown spec) and
generates requests from it. The rest of the loop is unchanged.

---

## Bonus: fully automated loop

**Status: Implemented.**

The `/dev-loop` skill ends by asking "Run another cycle?" — if yes, it loops
back to Step 1 automatically. The `AskUserQuestion` approval gate (Step 3 of
each cycle) is the only blocking step.

For a fully hands-off loop (Ctrl+C to stop), use the built-in `/loop` skill:

```bash
# In Claude Code:
/loop /dev-loop
```

This runs `/dev-loop` repeatedly. Each iteration stops only at the feature-approval
gate. Press Ctrl+C at any time to exit.

Alternatively, from the shell:

```bash
while true; do
    claude --print "/dev-loop"
done
```

---

## File structure

```
quanted/
├── CLAUDE.md                          # Project conventions + quick-start
├── SETUP.md                           # This file
├── CHANGELOG.md                       # Feature history (updated each cycle)
├── requirements.txt                   # Python dependencies
├── usage_log.jsonl                    # Append-only usage signal (auto-created)
├── app/
│   └── main.py                        # FastAPI app: calculator + middleware
├── scripts/
│   └── simulate.py                    # Schema-driven simulator
├── tests/
│   └── test_calculator.py             # FastAPI TestClient tests
└── .claude/
    ├── agents/
    │   ├── feature-suggester.md       # Read-only: analyzes usage, proposes features
    │   ├── implementer.md             # Read-only: returns code + test + changelog
    │   └── docs-updater.md            # Read-only: returns OpenAPI metadata patches
    └── skills/
        ├── simulate/
        │   └── SKILL.md               # /simulate — runs the simulator
        └── dev-loop/
            └── SKILL.md               # /dev-loop — full orchestrator cycle
```
