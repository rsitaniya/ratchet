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

**Bonus — run cycles continuously with Claude Code's built-in loop runner:**
```
/loop /dev-loop
```

The loop will:
1. Simulate API traffic → populates `usage_log.jsonl`
2. Invoke the feature-suggester → returns 2-3 proposals grounded in the data
3. **Stop and ask you to pick a feature** ← only blocking step
4. Invoke the implementer → returns a standard unified diff + metadata
5. Orchestrator validates/applies the diff with `git apply --check` + `git apply`, runs `pytest`, confirms tests pass
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
    │       runs:    scripts/analyze_usage.py (signal report)               │
    │       reads:   app/main.py (skips already-implemented features)       │
    │       returns: PROPOSALS block (2-3 options with signal + complexity) │
    │   ◄───────────────────────────────────────────────────────────────────┘
    │
    ├─ [AskUserQuestion] ⏸ HUMAN PICKS ONE FEATURE (or "Skip this cycle")
    │
    ├─ [Agent] implementer ─────────────────────────────────────────────────┐
    │       reads: app/main.py (for style/context)                          │
    │       returns: unified diff + TEST_FILE + CHANGELOG + EDGE_CASES JSON   │
    │   ◄───────────────────────────────────────────────────────────────────┘
    │
    ├─ [Bash] git apply --check + git apply for code/test patch
    ├─ [Edit] Orchestrator applies changelog/version/edge-case metadata
    ├─ [Bash] pytest tests/ -v  ← must pass before continuing
    ├─ [Bash] restart uvicorn
    │
    ├─ [Agent] docs-updater ────────────────────────────────────────────────┐
    │       reads: app/main.py                                              │
    │       returns: unified diff for OpenAPI metadata, or NO_CHANGES_NEEDED │
    │   ◄───────────────────────────────────────────────────────────────────┘
    │
    ├─ [Bash] git apply --check + git apply for metadata patch
    └─ [Bash] simulator re-run → confirms new endpoint in /openapi.json

Continuous mode is supplied by Claude Code's built-in `/loop` runner:
`/loop /dev-loop`.
```

**Key design: subagents are read-only planners.** They return standard patch artifacts;
the orchestrator applies every file write. This means:
- No permission prompts inside subagents
- Single point of control for all mutations
- Clean, auditable handoffs — unified diff + JSON metadata is the contract
- Repeatable patch application — every subagent diff is checked with `git apply --check`
  before it mutates the worktree

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
request to a **product endpoint** — everything except a small infra skip-list
(`SKIP_USAGE_PATHS`: `/health`, `/docs`, `/redoc`, `/openapi.json`, …) — and appends
a JSON record to `usage_log.jsonl`:

```json
{
  "timestamp": "2026-06-16T10:23:45.123Z",
  "path": "/calculate",
  "method": "GET",
  "operation": "divide",
  "inputs": {"op": "divide", "a": "10", "b": "0"},
  "status_code": 400,
  "latency_ms": 1.23,
  "error_type": "DivisionByZero",
  "source": "simulator"
}
```

`inputs` captures all query params generically, so the record shape is the same
for any endpoint. The file is append-only; historical entries accumulate across cycles.

### Endpoint-generic by design — the loop self-feeds for any feature shape

Recording is keyed off the request path, not hardcoded to `/calculate`. This is what
makes the loop genuinely self-feeding for **any** feature, not just new `op` values:

- A new endpoint shipped by the loop (e.g. `GET /sqrt`) is exercised by the simulator
  *and* its traffic (`path: /sqrt`, status, latency) is recorded — so the next cycle's
  suggester sees its real usage and can refine it.
- A request to a path that **doesn't exist yet** is recorded as a 404. `analyze_usage.py`
  surfaces these under **"Requested-but-missing endpoints"** — direct demand signal that
  says "build this endpoint." (See `tests/test_usage_logging.py` for the functional proof.)

### The `source` field — keeping signal honest

Each record carries a `source` (`simulator` | `unknown`), taken from the
`X-Usage-Source` request header. The simulator sets it; ad-hoc/real callers
default to `unknown`. This lets `analyze_usage.py --source simulator` separate
generated traffic from organic traffic.

**Test traffic never reaches this file.** `tests/conftest.py` redirects
`USAGE_LOG` to a temp path for the whole test session, so running `pytest`
cannot pollute the product signal that the feature-suggester reads.

### `analyze_usage.py` — raw log → actionable signal

The feature-suggester does not read raw JSONL. It runs `scripts/analyze_usage.py`,
which produces a per-endpoint/operation table (call volume, error rate, error-type
breakdown — keyed by `op` for `/calculate` and by `path` for other endpoints),
flags likely-unsupported operations (100% HTTP 422), lists requested-but-missing
endpoints (HTTP 404), and surfaces input-distribution signals (b=0 rate, negatives).
This mirrors how a PM reads an event stream: rates and failed-intent signals, not
individual log lines.

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
- `analyze_usage.py` parses it into a signal report with no DB or query engine
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
| `.claude/skills/dev-loop/SKILL.md` | Native Claude Code skill | Orchestrates one complete cycle; has access to `AskUserQuestion` for the approval gate |
| `.claude/agents/feature-suggester.md` | Native Claude Code subagent | Scoped read-only tools; clear system prompt; invoked via `Agent` tool from orchestrator |
| `.claude/agents/implementer.md` | Native Claude Code subagent | Read-only — returns unified diff + metadata the orchestrator validates and applies |
| `.claude/agents/docs-updater.md` | Native Claude Code subagent | Read-only — returns a unified diff for OpenAPI metadata |
| Claude Code `/loop` | Built-in Claude Code loop runner | Provides the deterministic continuous runtime wrapper for the bonus command |
| FastAPI `TestClient` | FastAPI built-in | In-process tests; no live server needed; idiomatic for FastAPI projects |
| `scripts/simulate.py` | Plain Python + httpx | Generic multi-endpoint simulator; discovers every path+method from `/openapi.json` and synthesizes requests from their schemas |

**Why native Claude Code skills/subagents plus `/loop`:**
The `.claude/skills/<name>/SKILL.md` + `.claude/agents/<name>.md` convention
is Claude Code's built-in orchestration layer. `/loop` is Claude Code's existing
runtime loop framework, so the continuous bonus is not a hand-rolled `while true`
script. This keeps the solution convention-aware without adding a heavyweight
external framework (LangGraph, CrewAI, etc.) inside a 150-minute time box.

---

## How to adapt this setup to a different API

The only components that are calculator-specific:

1. **`app/main.py`** — replace entirely with your API.
2. **`DOMAIN_EDGE_CASES` dict in `scripts/simulate.py`** — an *optional* overlay of
   correlated edge cases keyed by an enum value (here, the `op` query param: e.g.
   `divide` → `{"a": 10, "b": 0}`). Replace with your domain's interesting inputs,
   or delete it — the simulator still works from the schema alone.
3. **`SKIP_USAGE_PATHS` in `app/main.py`** — the usage middleware records *every*
   endpoint except this infra skip-list (`/health`, `/docs`, `/openapi.json`, …).
   For a different API, just adjust which paths count as infra noise; all product
   endpoints are captured automatically with no per-endpoint wiring.

Everything else is generic by construction:

- **The simulator reads `/openapi.json` and exercises every path + method it finds**,
  synthesizing query params, path params, and JSON request bodies directly from their
  schemas (`$ref`, `enum`, arrays, and nested objects are all resolved). A brand-new
  endpoint — a `GET`, or a `POST` with a body, or one with path params — is exercised
  automatically on the next cycle with **no edits to the simulator**. (Verified against
  a synthetic `POST /batch` + `GET /history/{id}` schema.)
- The feature-suggester prompt works for any `usage_log.jsonl` with the same record shape
- The implementer and docs-updater prompts are FastAPI-oriented but apply to any Python/FastAPI service
- The dev-loop orchestrator is fully generic — it applies whatever structured text the subagents return

**Signal and exercise are both endpoint-generic.** The simulator *exercises* every
endpoint discovered from `/openapi.json`, and the middleware *records* every product
endpoint (everything outside `SKIP_USAGE_PATHS`). So a newly-shipped endpoint of any
shape is both hit and turned into signal on the next cycle — no per-endpoint wiring —
and even requests to paths that don't exist yet are captured as 404 demand signal.

**To target a non-OpenAPI API:** swap the schema source in `simulate.py` (e.g. fetch a
Postman collection or a custom spec) and keep the same generate-from-schema logic. The
rest of the loop is unchanged.

---

## Bonus: fully automated loop

**Status: Implemented.**

`/dev-loop` performs one complete, test-gated cycle. The continuous runtime loop is
Claude Code's built-in `/loop` runner:

```
/loop /dev-loop
```

That single command keeps launching cycles until you stop it. The `AskUserQuestion`
approval gate (STEP 3) is the **only** blocking step. Every other step — simulate,
suggest, implement, test, restart, docs, verify — chains automatically inside each
cycle. To exit the loop:

- Choose **"Skip this cycle"** at the STEP 3 approval gate (graceful), or
- Press **Ctrl+C** at any time.

---

## File structure

```
quanted/
├── CLAUDE.md            # Project conventions + quick-start
├── SETUP.md             # This file
├── CHANGELOG.md         # Feature history — a release section per shipped cycle
├── requirements.txt     # Python dependencies
├── pyproject.toml       # pytest config (pythonpath = ["."])
├── .gitignore           # Ignores caches, venvs, zips, runtime usage_log.jsonl
├── usage_log.jsonl      # Runtime usage signal (gitignored; auto-created on first run)
├── app/                 # FastAPI app: calculator + usage middleware (main.py)
├── scripts/             # simulate.py (schema-driven simulator) + analyze_usage.py (signal report)
├── tests/               # FastAPI TestClient suites + conftest.py (shared client, usage_log isolation)
│                        #   one test_<feature>.py is added per shipped cycle
└── .claude/
    ├── agents/          # Read-only subagents: feature-suggester, implementer, docs-updater
    └── skills/          # /simulate and /dev-loop orchestrator
```

> The `tests/`, `scripts/`, and `app/` contents grow as the loop ships features
> (each cycle adds a `test_<feature>.py`), so this tree is described by directory
> rather than enumerated file-by-file — it stays accurate as the loop runs.
