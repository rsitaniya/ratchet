# Real forbes — attended run

**Purpose:** onboard MaDI-Bench's real `forbes` source from an empty adapter,
through both human gates, with every cycle receipted.

`flywheel.real.toml` selects MaDI-Bench's 2,000-record Forbes CSV, its
schema-mapping gold, and `adapters_real/forbes.toml`. The real raw columns
share no names with the synthetic Forbes fixture, so this is a separate
mapping task, not a subsample of the development data. Unlike `fullcontact`
(anonymized `Attribute_1..6` columns), `forbes`' own column names are
self-descriptive — `company`, `asset_value`, `sales_figure` — which is why the
[case study](../../CASE_STUDY.md#what-integrated_rate-is-actually-measuring)
calls it the lower-ambiguity of the two real splits.

Only schema-mapping gold is available. `value_recall` and `fully_correct_rate`
are `null`, meaning unmeasured, not zero quality.

This is a distinct measurement from the [convergence trials](../trials/README.md):
those auto-answer both gates and revert every run, so they measure whether the
implementer converges at all, not whether a reviewed change is correct. Every
cycle here was answered by an operator at the terminal and kept.

## What it reached

| Cycle | schema_f1 | Fields mapped that cycle |
|---|---:|---|
| 00 | `0.0000` | — (empty adapter) |
| 01 | `0.6667` | `name`, `assets`, `revenue` |
| 02 | `0.8000` | `id` |

Cycle 02's fix was as much a correction as an addition. Cycle 01's adapter
comment had declared `id` unmappable, blaming `adapters.py`'s `apply_adapter()`
skip of the literal `record_id` key. That was wrong: `record_id` is pipeline
metadata `to_replay.py` synthesizes only for live `/ingest` traffic and never
appears on the raw source rows the held-out evaluator scores, so it was never
a candidate for `id` in the first place — its presence or absence in
`apply_adapter()`'s skip list has no bearing on what the evaluator can score.
Before touching the adapter, a scratch copy with `forbes_url → id` (`identity`)
was scored against the held-out evaluator without ever reading gold content:
`schema_f1` moved `0.6667 → 0.8000`, exactly the value predicted if that guess
scored precision-1.0 against a 6-attribute gold set. Only after that
confirmation did the change land for real.

Per-field yield at the current state — the share of the 2,000 records that
actually produced a value. It needs no gold and is the number to read first:

| Target | Source column | Produced | Rate |
|---|---|---:|---:|
| `id` | `forbes_url` | 2000 / 2000 | 1.0000 |
| `name` | `company` | 2000 / 2000 | 1.0000 |
| `assets` | `asset_value` | 2000 / 2000 | 1.0000 |
| `revenue` | `sales_figure` | 2000 / 2000 | 1.0000 |

`02_cycle2.gaps.txt` still carries three `UNMAPPED_FIELD` rows (`url`,
`region`, `business_segment`) and four `MISSING_REQUIRED_FIELD` rows
(`founded`, `country`, `city`, `industry`) — this run has not converged the
source, only fixed a wrong claim about why `id` couldn't be. `country` and
`industry` are mappable in a future cycle (`region → country` via the existing
`country_to_iso` table matches 84.3% of real values; `business_segment →
industry` via `non_placeholder_str` covers 97.9%). `founded` and `city` are
structurally unsatisfiable: `evaluate_source` reports `integrated_ceiling`
`0.0` with `unsatisfiable_required` naming both — no cycle can move that, since
gold has no forbes column for either. See
[what `integrated_rate` is actually measuring](../../CASE_STUDY.md#what-integrated_rate-is-actually-measuring).

## What it cost

| Cycle | Outcome | Wall | Agent | Gate 1 | Gate 2 |
|---|---|---:|---:|---:|---:|
| 1 | kept | 490.96s | 234.66s | 121.11s | 135.19s |
| 2 | kept | 520.55s | 100.57s | 141.41s | 278.57s |

These are cycles 4 and 5 in [`../delivery/cycles.jsonl`](../delivery/cycles.jsonl)
(the shared delivery log every config appends to) — locally numbered 1 and 2
here since they are this split's first two cycles. Derived by
`scripts/cycle_log.py report`: 2 of 2 accepted at Gate 2, 0 resubmissions, 0
control stops. The agent-minutes and wall-minutes per accepted change derived
from these records, combined with the three `fullcontact` cycles, are
published in the README and CASE_STUDY, and CI recomputes both from that file
and fails on drift.

Zero control stops is a limit of this set, not evidence the controls are
unnecessary: no cycle attempted a protected path or regressed an onboarded
field.

## What is in each cycle

`NN.adapter.toml` is the adapter as it stood after that cycle; `NN.adapter.diff`
is the change from the previous snapshot and `NN.diff_hash.txt` its
`git hash-object`; `NN.evaluate.json` is the held-out evaluator's output
against all 2,000 real records; `NN.gaps.txt` is the integration gap report
from replaying the 300-record traffic sample
(`replay_real_forbes.jsonl`) through the live app with a cycle-isolated
`--run-id`, filtered with `analyze_integration.py --source forbes --run-id
<id>` so each file reflects only that cycle's adapter state, not the
cumulative usage log.

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

The command above reproduces `NN.evaluate.json` against the committed adapter
snapshot at each cycle (swap `adapters_real` for a copy of the relevant
`NN.adapter.toml` to reproduce an earlier cycle's score). `NN.gaps.txt` needs
the live app: point `ADAPTERS_DIR` at the same snapshot, restart the server,
run `uv run python scripts/simulate.py --replay
engagements/madi_onboarding/replay_real_forbes.jsonl --run-id <id>`, then
`analyze_integration.py "$USAGE_LOG_PATH" --source forbes --run-id <id>`.

CI does not recompute these receipts the way it recomputes `runs/forbes/` and
`runs/reconcile/`: `data/madi/` is gitignored, fetched by `download_data.py`
against pinned git blob SHAs, and that download step is deliberately non-fatal
so an external outage never reds the build. The delivery figures derived from
this run *are* machine-checked — `scripts/render_delivery_table.py --check`
and the README economics check both fail CI on drift.
