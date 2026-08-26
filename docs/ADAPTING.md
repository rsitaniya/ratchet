# Adapting the flywheel to your own API

The loop carries no knowledge of the bundled calculator. Everything domain-specific
lives in **two files at the repo root** — `flywheel.toml` and `edge_cases.json`.
Nothing under `scripts/` or `.claude/` should need to change.

This is enforced by construction, not by convention: the simulator derives every
request from your `/openapi.json` at runtime, and the analyzer keys its report by
`operation` where present and `path` otherwise. Both were verified to run against
an API with **no config file and no edge cases at all**.

---

## Step 1 — Point `flywheel.toml` at your app

```toml
[app]
module = "myservice.api:app"          # what uvicorn serves
base_url = "http://localhost:8000"
version_files = ["myservice/api.py", "pyproject.toml", "CHANGELOG.md"]
```

`version_files` is the list the orchestrator bumps each cycle, so your running
app's `/openapi.json` always reports the version the CHANGELOG just released.

## Step 2 — Seed `edge_cases.json` (optional)

The simulator already exercises every endpoint using values synthesized from your
schema. This file only adds **correlated** cases — combinations that random values
would rarely produce but that generate the most interesting signal:

```json
{
  "refund": [
    { "amount": 0, "currency": "USD" },
    { "amount": -1, "currency": "USD" }
  ]
}
```

Keyed by the value of any enum-driven param your schema exposes. When the simulator
generates a request carrying that value, it overlays one of these (40% of the time).

**Delete this file and everything still works** — you just get schema-random inputs
instead of curated ones. The dev-loop appends to it automatically as it ships features,
so it grows itself over time.

## Step 3 — Declare which inputs are signal (optional)

```toml
[signals]
numeric_params = ["amount"]      # report how often each is negative
zero_value_params = ["amount"]   # report how often each is exactly zero
```

Leave both empty and the "Input signals" section simply reports nothing. This exists
because for some APIs the *distribution* of inputs is itself the product signal — in
the bundled calculator, a spike in `b=0` is what surfaced demand for `safe_divide`,
and a spike in negative `a` is what surfaced demand for `abs`.

## Step 4 — Run the loop

```bash
uvicorn "$(python scripts/flywheel_config.py --get app.module)" --reload
/dev-loop
```

To run the loop against a *second* app without disturbing the first, put its
config in its own file and select it per-invocation:

```bash
export FLYWHEEL_CONFIG=path/to/your/flywheel.toml
```

`FLYWHEEL_CONFIG` (or an explicit path arg) beats the repo-root `flywheel.toml`,
and path-valued keys (`usage_log`, `edge_cases`, `traffic.replay_file`) resolve
against that config file's own directory.

---

## What stays generic (and why you don't touch it)

| Piece | Why it needs no edits |
|---|---|
| `scripts/simulate.py` | Walks every path + method in `/openapi.json`; synthesizes values from JSON Schema (`$ref`, `enum`, `anyOf`/`oneOf`/`allOf`, arrays, nested objects). A new endpoint is exercised on the next cycle automatically. |
| `scripts/analyze_usage.py` | Keys by `operation` or `path`; surfaces 404s as demand signal. |
| Usage middleware | Records every path outside `SKIP_USAGE_PATHS` generically, including 404s. |
| `.claude/skills/`, `.claude/agents/` | Read paths and version files from `flywheel.toml`. |

## The one thing your app must provide

A **usage middleware** that appends one JSON line per request to `usage_log.jsonl`.
The loop's entire signal comes from this file. Copy the middleware from
`app/main.py` (search for `@app.middleware("http")`) — it is ~20 lines and already
endpoint-generic. It must record at minimum:

```json
{"timestamp": "...", "path": "/refund", "method": "POST", "operation": null,
 "inputs": {}, "status_code": 404, "latency_ms": 0.4, "error_type": null, "source": "simulator"}
```

Recording **404s is deliberate and load-bearing** — a request to an endpoint you
haven't built is the strongest possible signal that someone wants it. Don't filter
those out.

---

## Going further: engagements with a held-out oracle

The calculator improves by adding endpoints, scored only by "does it 404 less."
For domains where correctness matters, package the app plus its own analyzer and a
**held-out evaluator** as an engagement — see `engagements/madi_onboarding/` for a
worked example (partner-data onboarding, scored against gold labels).

The extra pieces, all generic to the loop:

- **`[app].evaluator`** — a command the loop runs at Gate 2 to score a proposed
  patch against held-out truth (schema F1, value accuracy, regression), not just
  HTTP status. Leave it empty and the loop behaves as before. The orchestrator
  snapshots the evaluator's output on the clean pre-cycle tree (STEP 1) and, on
  every later cycle, re-invokes the evaluator with `--baseline <that snapshot>` at
  Gate 2 — so a source that already worked and got worse is a hard gate failure,
  not a silent one. Your evaluator only needs to accept that flag and, when
  present, add a `"regression": true/false` key to its JSON output (see
  `engagements/madi_onboarding/evaluate.py` for the reference implementation).
- **`[protected].paths`** — globs the implementer patch may never touch (the
  evaluator, gold labels, fixtures, scoring). `scripts/check_protected_paths.py`
  rejects violating patches before `git apply`, so the loop can't pass by editing
  what measures it.
- **A domain analyzer** the feature-suggester is pointed at (the de-hardcoded
  agents read whatever app/analyzer they're handed), for signal richer than HTTP
  status — e.g. field-level integration failures.
- **Declarative growth** — design the app to read config the loop can extend
  (adapters, rules) so most cycles ship *data*, not agent-written code.

Licensed benchmark data is never committed; ship a checksum-pinned downloader
instead (`engagements/madi_onboarding/download_data.py`).
