# real_forbes — the test split's baseline receipt

Same mechanism as `runs/forbes/`, run against real data instead of the synthetic
fixtures: `flywheel.real.toml` points the app at MaDI-Bench's own forbes CSV
(2000 records, `data/madi/`) and at `adapters_real/forbes.toml`, and the evaluator
scores against `data/madi/gold_mapping.json` (MaDI's own `sm_mapping_gold.json`,
filtered to positive correspondences) — never the synthetic gold.

Real forbes columns (`forbes_url, company, url, region, business_segment,
asset_value, sales_figure`) share nothing with the synthetic forbes adapter, so
this is a genuine held-out distribution, not a subsample: the synthetic adapter
cannot transfer here.

Only the schema-matching gold is pinned for the real benchmark — no normalized
value gold — so `value_recall` and `fully_correct_rate` report `null` here, not
`0.0` (`0.0` would misrepresent "unmeasured" as "totally wrong"). This is the
test split: scored once here to establish the baseline, not scored on every dev
cycle the way `runs/forbes/` is.

## 00_baseline

- `00_baseline.adapter.toml` — the starting adapter: no field mappings, same
  shape as `adapters/forbes.toml`'s synthetic counterpart.
- `00_baseline.gap_report.txt` — 300 real forbes records replayed through
  `POST /ingest` (bounded telemetry sample; the evaluator scores all 2000
  records offline regardless of how many were replayed).
- `00_baseline.evaluate.json` — `evaluate.py --fixtures data/madi --adapters
  adapters_real --sources forbes` against all 2000 real records:
  `schema_f1=0.0`, `integrated_rate=0.0`, `value_recall`/`fully_correct_rate`
  `null` — the expected starting point for an empty adapter.

No diff yet: this is the pre-cycle baseline, not a converged cycle. Phase 3's
trial runs start from exactly this adapter and this baseline.

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
