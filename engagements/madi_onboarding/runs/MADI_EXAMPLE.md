# Synthetic-cycle receipts

**What this proves:** the documented onboarding and reconciliation changes reproduce from their committed inputs. Each receipt links the input state, gap report, change artifact, hash, and evaluator output.

These are raw records for the [README](../../../README.md) and [case study](../CASE_STUDY.md). The numbers below are literal `evaluate.py` output from the committed adapter or rule snapshot beside them. They establish reproducibility on the synthetic split. They do not establish the real-data trial result, scale, or customer impact.

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
| value recall (vs gold) | 0.0 | 0.375 | 1.0 |
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

## reconcile (entity matching + data fusion)

| Cycle | Rules changed | Gaps that motivated it | Diff (hash) | Evaluator output |
|---|---|---|---|---|
| Baseline | [matching](reconcile/00_baseline.matching_rules.toml) + [fusion](reconcile/00_baseline.fusion_rules.toml) | — | — | [00_baseline.evaluate.json](reconcile/00_baseline.evaluate.json) |
| Cycle 1 | [matching_rules.toml](reconcile/01_cycle1.matching_rules.toml) | [01_cycle1.gaps.txt](reconcile/01_cycle1.gaps.txt) | [01_cycle1.matching_rules.diff](reconcile/01_cycle1.matching_rules.diff) (`eb91dd90`) | [01_cycle1.evaluate.json](reconcile/01_cycle1.evaluate.json) |
| Cycle 2 | [fusion_rules.toml](reconcile/02_cycle2.fusion_rules.toml) | [02_cycle2.gaps.txt](reconcile/02_cycle2.gaps.txt) | [02_cycle2.fusion_rules.diff](reconcile/02_cycle2.fusion_rules.diff) (`4bb579b6`) | [02_cycle2.evaluate.json](reconcile/02_cycle2.evaluate.json) |

| `reconcile` metric | Baseline | Cycle 1 | Cycle 2 |
|---|---:|---:|---:|
| entity-matching F1 | 0.0 | 1.0 | 1.0 |
| fusion accuracy | 0.875 | 0.875 | 1.0 |
| `dbpedia`/`forbes` regression | — | none (`"regression": false`) | none (`"regression": false`) |

Cycle 1's gaps report has an empty fusion-conflicts section on the baseline run and only
becomes non-empty once matching finds pairs — `summarize_reconcile()` computes fusion
conflicts from *matched* pairs' telemetry, so live signal can't surface a fusion problem
before matching works. That is why the cycles are ordered matching-then-fusion here, unlike
`evaluate_reconcile()`'s own fusion metric, which is deliberately scored against gold-matched
clusters so it stays visible independent of matching quality (see `evaluate.py`).

Reproduce cycle 1's gap report:

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
export USAGE_LOG_PATH=$(uv run python scripts/flywheel_config.py --get app.usage_log)
cp engagements/madi_onboarding/runs/reconcile/01_cycle1.matching_rules.toml engagements/madi_onboarding/matching_rules.toml
uv run uvicorn "$(uv run python scripts/flywheel_config.py --get app.module)" --port 8000 &   # wait for /health
# POST fixtures/reconcile/{left,right}.jsonl to /reconcile with X-Run-Id: <id>
uv run python engagements/madi_onboarding/analyze_integration.py "$USAGE_LOG_PATH" --reconcile --run-id <id>
git checkout engagements/madi_onboarding/matching_rules.toml
```

Reproduce the evaluator output for either cycle:

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
cp engagements/madi_onboarding/runs/reconcile/01_cycle1.matching_rules.toml engagements/madi_onboarding/matching_rules.toml
uv run python engagements/madi_onboarding/evaluate.py --baseline engagements/madi_onboarding/runs/reconcile/00_baseline.evaluate.json
# → matches 01_cycle1.evaluate.json's "reconcile" key
git checkout engagements/madi_onboarding/matching_rules.toml
```

Add `fusion_rules.toml` from `02_cycle2.fusion_rules.toml` on top of the cycle-1 matching
rules (baseline `01_cycle1.evaluate.json`) for the second row. Both committed rule files ship
as the weak seed for the same reason the forbes adapter ships empty: so a reader starts from
the same zero state these receipts did.

## How the gap reports were produced

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
export USAGE_LOG_PATH=$(uv run python scripts/flywheel_config.py --get app.usage_log)
uv run python engagements/madi_onboarding/to_replay.py --source forbes
uv run uvicorn "$(uv run python scripts/flywheel_config.py --get app.module)" --port 8000 &   # wait for /health
uv run python scripts/simulate.py --replay engagements/madi_onboarding/replay_forbes.jsonl --run-id <id> http://localhost:8000
uv run python engagements/madi_onboarding/analyze_integration.py "$USAGE_LOG_PATH" --source forbes --run-id <id>
```

## Reproduce the evaluator output

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
cp engagements/madi_onboarding/runs/forbes/01_cycle1.adapter.toml engagements/madi_onboarding/adapters/forbes.toml
uv run python engagements/madi_onboarding/evaluate.py --baseline engagements/madi_onboarding/runs/forbes/00_baseline.evaluate.json
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

## Real-data test split: forbes

`runs/real_forbes/` — the same mechanism, run against MaDI-Bench's own forbes CSV (2000 records)
and its own schema-matching gold instead of the synthetic fixtures above, selected by
`FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real.toml`. Two human-gated `/dev-loop`
cycles have landed on it (`schema_f1` `0.0 → 0.6667 → 0.8`), each scoring the held-out
evaluator for real at Gate 2, the same as the synthetic cycles above. See
[runs/real_forbes/README.md](real_forbes/README.md) and the case study's
[separate real-data measurement section](../CASE_STUDY.md#separate-real-data-measurement).
