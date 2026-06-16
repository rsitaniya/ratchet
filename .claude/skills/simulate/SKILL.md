---
name: simulate
description: Schema-driven API simulator. Fetches /openapi.json, discovers operations, fires realistic + edge-case requests to populate usage_log.jsonl.
allowed-tools: Bash, Read
---

# Simulator Skill

Run the schema-driven simulator against the running FastAPI calculator.

## Steps

### 1. Verify the server is running

```bash
curl -s http://localhost:8000/health
```

If the server is not running, tell the user:
> The API server is not running. Start it with:
> `uvicorn app.main:app --reload`
> Then invoke `/simulate` again.

Do not proceed if the server is unreachable.

### 2. Show the current schema paths

```bash
curl -s http://localhost:8000/openapi.json | python3 -c "
import json, sys
schema = json.load(sys.stdin)
print('API title:', schema['info']['title'], 'v' + schema['info']['version'])
print('Paths:', list(schema['paths'].keys()))
"
```

### 3. Run the simulator

```bash
python scripts/simulate.py http://localhost:8000 30
```

This script:
- Fetches `/openapi.json` and parses the `op` enum to discover all available operations
- Generates 30 requests: 60% random realistic inputs, 40% targeted edge cases (zero divisor, negatives, floats, large numbers)
- Prints a per-request log and a summary table
- Every request is recorded to `usage_log.jsonl` via the API's usage middleware

### 4. Report

After the simulator finishes, report:
- How many requests were fired per operation
- Error rate per operation (especially divide-by-zero rate)
- Any new operations discovered vs. previous cycle
- Current line count in usage_log.jsonl

```bash
wc -l usage_log.jsonl 2>/dev/null || echo "usage_log.jsonl not yet created"
```

The simulation is complete. Usage data is ready for the feature-suggester.
To run the full agentic cycle, invoke `/dev-loop`.
