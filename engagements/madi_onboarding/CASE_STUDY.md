# Case study: onboarding a new partner data source with the flywheel

**What this shows:** dev-flywheel pointed at a partner-data onboarding API,
growing a new source's integration from **0% to 100% correct** across two
approved cycles — scored the whole way against **held-out gold labels** the loop
is forbidden to touch. This is a reproducible benchmark of the loop's decisions,
not a business-impact claim.

## The setup

A partner-onboarding service exposes one stable endpoint, `POST /ingest`. It maps
and normalizes each partner record to a canonical company schema (`name, founded,
country, city, industry, assets, revenue, keypeople`) using a per-source
**adapter** — declarative data the loop grows. One source (`dbpedia`) is already
onboarded. A second (`forbes`) arrives with different field names and messy
formats: `yearFounded` as a string, `country` as `"United States"`, `assets` as
`"$1.2B"`, and `sales` where the target wants `revenue`.

The benchmark is modeled on the Companies task of [MaDI-Bench](https://github.com/wbsg-uni-mannheim/MaDI-Bench)
(schema matching + value normalization). The numbers below use this repo's own
synthetic fixtures; `download_data.py` runs the identical pipeline against the
real, licensed MaDI data (see [DATA_LICENSE_NOTICE.md](DATA_LICENSE_NOTICE.md)).

## The loop, per cycle

1. Replay the new source's records at `/ingest`. Every record fails, emitting
   structured signal: `UNMAPPED_FIELD`, `INVALID_VALUE_FORMAT`,
   `MISSING_REQUIRED_FIELD` — field-level, privacy-preserving (hashed ids, no raw
   values).
2. `analyze_integration.py` ranks the gaps by how many records each affects.
3. The planner proposes **one** adapter change, citing the counts. **Gate 1:** a
   human approves the proposal.
4. The implementer returns the adapter patch. The orchestrator runs
   `check_protected_paths.py` — the patch may touch adapters but **never** the
   evaluator, gold, or fixtures — then applies it.
5. The **held-out evaluator** scores the change against gold and checks the seed
   source for regression. **Gate 2:** a human approves the exact tested patch.
6. Replay again; measure.

## Results (real numbers from `evaluate.py`)

| `forbes` metric        | Baseline | Cycle 1 | Cycle 2 |
|------------------------|---------:|--------:|--------:|
| schema-mapping F1      |     0.00 |    0.55 |    1.00 |
| value recall (vs gold) |     0.00 |       — |    1.00 |
| integrated rate        |       0% |    100% |    100% |
| fully-correct rate     |       0% |      0% |    100% |
| `dbpedia` regression   |        — |    none |    none |

- **Cycle 1** mapped the three required fields (`name`, `yearFounded→founded`,
  `country`). Integration jumped 0% → 100% (every record now produces the
  required target attributes), but fully-correct stayed 0% — optional fields were
  still unmapped, and the oracle counts a record correct only when *every* gold
  attribute matches.
- **Cycle 2** mapped the rest, including the two that need real judgment: the
  semantic rename `sales → revenue`, and currency/ISO normalization. Schema F1
  and value recall (share of gold values reproduced) reached 1.00.
- **No regression:** `dbpedia` stayed at 1.00 throughout. The onboarding didn't
  break the source already in production.

## Why the metrics can't be gamed

The evaluator reads the source records, the current adapters, and the **gold
labels** — never the telemetry the app wrote — so its verdict is independent of
the telemetry and of the gold. Returning HTTP 200 for everything would not move
schema F1 or value recall one point. The orchestrator forbids the implementer
from editing the scorer, the mapping engine it runs, the fixtures, or the gold:
a patch that **modifies, renames, or deletes** `evaluate.py`, `adapters.py`,
`fixtures/`, or gold is rejected before apply (verified — the checker exits 2 on
modify, rename, and delete diffs). What the loop *can* write — adapter mappings
and new normalizers — can't inflate the score either: gold is unreachable, and a
wrong normalizer only lowers value recall. A plausible-but-wrong mapping is
caught too: pointing `sales → assets` instead of `revenue` drops both schema F1
and fully-correct rate.

## Honest limits

- These are results on a small fixture (7 companies) and, with the downloader, on
  MaDI-Bench's Companies task. They measure schema matching + value normalization
  (Stage 1). Entity matching and data fusion — where MaDI's baselines are far from
  solved (fully-correct rate ~0.05) — are deliberately out of scope here.
- "Correct" means "matches gold." That is a real oracle, but it is a benchmark,
  not evidence of production value at a specific customer.
- The loop grows *declarative adapters*; a genuinely new normalizer is the only
  case that produces agent-written code, and it goes through the evaluator and
  both gates.

## Reproduce

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
export USAGE_LOG_PATH=$(python scripts/flywheel_config.py --get app.usage_log)
python engagements/madi_onboarding/to_replay.py --source forbes
uvicorn "$(python scripts/flywheel_config.py --get app.module)" --port 8000 &   # wait for /health
python scripts/simulate.py --run-id onboard-baseline
python engagements/madi_onboarding/analyze_integration.py "$USAGE_LOG_PATH" --source forbes
python engagements/madi_onboarding/evaluate.py        # baseline: forbes all zero
# then run /dev-loop to have the agent grow adapters/forbes.toml, or edit it by hand
```
