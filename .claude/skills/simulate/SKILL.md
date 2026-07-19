---
name: simulate
description: Schema-driven API simulator. Fetches /openapi.json, discovers operations, fires realistic + edge-case requests to populate the usage log.
allowed-tools: Bash, Read
---

# Simulator Skill

Run the schema-driven simulator against the running FastAPI app. Which app,
base URL, and usage-log path all come from the active `flywheel.toml` (selected
by `$FLYWHEEL_CONFIG`, else the repo-root file) — nothing here is app-specific.

## Steps

### 1. Verify the server is running

```bash
BASE_URL=$(python scripts/flywheel_config.py --get app.base_url)
curl -s "$BASE_URL/health"
```

If the server is not running, tell the user:
> The API server is not running. Start it with:
> `export USAGE_LOG_PATH=$(python scripts/flywheel_config.py --get app.usage_log); uvicorn "$(python scripts/flywheel_config.py --get app.module)" --reload`
> Then invoke `/simulate` again.

Do not proceed if the server is unreachable.

### 2. Show the current schema paths

```bash
BASE_URL=$(python scripts/flywheel_config.py --get app.base_url)
curl -s "$BASE_URL/openapi.json" | python3 -c "
import json, sys
schema = json.load(sys.stdin)
print('API title:', schema['info']['title'], 'v' + schema['info']['version'])
print('Paths:', list(schema['paths'].keys()))
"
```

### 3. Run the simulator

```bash
python scripts/simulate.py
```

This script (no args → base URL and request count come from config):
- Fetches `/openapi.json` and walks every path + method to discover all operations
- Synthesizes requests from each operation's parameter and body schemas, biased toward boundary values that produce signal, plus any correlated edge cases in `[simulator].edge_cases`
- Prints a per-request log and a summary table
- Every request is recorded to the server's usage log via the app's usage middleware

To replay a fixed list of recorded requests instead of synthesizing them, pass
`--replay <file.jsonl>` (or set `[traffic].replay_file` in the config).

### 4. Report

After the simulator finishes, report:
- How many requests were fired per operation/path
- Error rate per operation/path (note any that error at a high rate)
- Any new operations discovered vs. previous cycle
- Current line count in the usage log

```bash
LOG=$(python scripts/flywheel_config.py --get app.usage_log)
wc -l "$LOG" 2>/dev/null || echo "usage log not yet created: $LOG"
```

The simulation is complete. Usage data is ready for the feature-suggester.
To run the full agentic cycle, invoke `/dev-loop`.
