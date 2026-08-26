# Run receipts

Committed evidence for the numbers in the top-level [README](../../../README.md#reference-engagement-partner-data-onboarding)
and [CASE_STUDY.md](../CASE_STUDY.md): the adapter at each cycle, the evaluator's
JSON output before and after, the gap report that motivated the cycle, and the
diff + its hash. Nothing here is asserted — every number is the literal output of
`evaluate.py` at HEAD, reproducible with the commands below.

## forbes onboarding (schema matching + value normalization)

| Cycle | Adapter | Gaps that motivated it | Diff (hash) | Evaluator output |
|---|---|---|---|---|
| Baseline | [00_baseline.adapter.toml](forbes/00_baseline.adapter.toml) | — | — | [00_baseline.evaluate.json](forbes/00_baseline.evaluate.json) |
| Cycle 1 | [01_cycle1.adapter.toml](forbes/01_cycle1.adapter.toml) | [01_cycle1.gaps.txt](forbes/01_cycle1.gaps.txt) | [01_cycle1.adapter.diff](forbes/01_cycle1.adapter.diff) (`22298265`) | [01_cycle1.evaluate.json](forbes/01_cycle1.evaluate.json) |
| Cycle 2 | [02_cycle2.adapter.toml](forbes/02_cycle2.adapter.toml) | [02_cycle2.gaps.txt](forbes/02_cycle2.gaps.txt) | [02_cycle2.adapter.diff](forbes/02_cycle2.adapter.diff) (`6de9c07e`) | [02_cycle2.evaluate.json](forbes/02_cycle2.evaluate.json) |

Real numbers, read straight from the JSON above:

| `forbes` metric | Baseline | Cycle 1 | Cycle 2 |
|---|---:|---:|---:|
| schema-mapping F1 | 0.0 | 0.5455 | 1.0 |
| value accuracy (vs gold) | 0.0 | 0.375 | 1.0 |
| integrated rate | 0.0 | 1.0 | 1.0 |
| fully-correct rate | 0.0 | 0.0 | 1.0 |
| `dbpedia` regression | — | none (`"regression": false`) | none (`"regression": false`) |

Each `NN_cycle*.evaluate.json` was produced with `--baseline` pointed at the
previous cycle's evaluator output, so `"regression": false` in the files
themselves is the same check `/dev-loop`'s Gate 2 now runs before a cycle can
land (see `.claude/skills/dev-loop/SKILL.md` STEP 6) — not a claim made
alongside the numbers, but the literal field they contain.

The evaluator's per-source F1 is computed against `fixtures/gold_mapping.json`
and `fixtures/gold_records.jsonl` — held out from this repo's own Claude Code
session by `.claude/settings.json` (`permissions.deny` on `**/fixtures/**` and
`**/gold_*.json`), so these receipts were built the same way the implementer
subagent would build them: from the adapter's ranked integration gaps
(`NN_cycle*.gaps.txt`, produced by replaying the raw source records at
`POST /ingest` and running `analyze_integration.py` — field names and error
codes only, never gold), never by reading the answer key.

## How the gap reports were produced

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
export USAGE_LOG_PATH=$(python scripts/flywheel_config.py --get app.usage_log)
python engagements/madi_onboarding/to_replay.py --source forbes
uvicorn "$(python scripts/flywheel_config.py --get app.module)" --port 8000 &   # wait for /health
python scripts/simulate.py --replay engagements/madi_onboarding/replay_forbes.jsonl --run-id <id> http://localhost:8000
python engagements/madi_onboarding/analyze_integration.py "$USAGE_LOG_PATH" --source forbes --run-id <id>
```

## Reproduce the evaluator output

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
cp engagements/madi_onboarding/runs/forbes/01_cycle1.adapter.toml engagements/madi_onboarding/adapters/forbes.toml
python engagements/madi_onboarding/evaluate.py --baseline engagements/madi_onboarding/runs/forbes/00_baseline.evaluate.json
# → matches 01_cycle1.evaluate.json
```

Swap in `02_cycle2.adapter.toml` (baseline `01_cycle1.evaluate.json`) for the
second row. Restore `git checkout engagements/madi_onboarding/adapters/forbes.toml`
afterward — **the committed adapter ships empty on purpose** (`0.0` across the
board, matching `00_baseline.evaluate.json`), so a reader can run the two cycles
themselves from the same zero state these receipts started from. Populating it
permanently would remove the thing the case study demonstrates.

## Regenerating live, instead of from these receipts

`FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml`, then run `/dev-loop`
against the shipped (empty) adapter — Gate 1 and Gate 2 walk the same two cycles
these receipts record, live, with the evaluator run for real at each Gate 2.
