# Real Forbes baseline

**Purpose:** establish the empty-adapter baseline for the separate real MaDI-Bench source distribution.

`flywheel.real.toml` selects MaDI-Bench’s 2,000-record Forbes CSV, its schema-mapping gold, and `adapters_real/forbes.toml`. The real raw columns share no names with the synthetic Forbes fixture. This makes the source a separate mapping task rather than a subsample of the development data.

Only schema-mapping gold is available. `value_recall` and `fully_correct_rate` are `null`, which means unmeasured. It does not mean zero quality.

## Baseline

| Metric | Result |
|---|---:|
| Schema-mapping F1 | 0.0 |
| Integrated rate | 0.0 |
| Value recall | null |
| Fully-correct rate | null |

The baseline adapter has no field mappings. `00_baseline.gap_report.txt` replays 300 records through `POST /ingest`. `00_baseline.evaluate.json` scores all 2,000 source records offline.

The baseline is a starting point, not a converged delivery result. See the [convergence trials](../trials/README.md) for the measured 5-run result and its limits.

## Reproduce

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real.toml
uv run python engagements/madi_onboarding/download_data.py
uv run python engagements/madi_onboarding/csv_to_ingest.py --source forbes
uv run python engagements/madi_onboarding/prepare_real_eval.py
uv run python engagements/madi_onboarding/evaluate.py \
  --fixtures engagements/madi_onboarding/data/madi \
  --adapters engagements/madi_onboarding/adapters_real --sources forbes
```
