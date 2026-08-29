# Real fullcontact — attended run

**Purpose:** onboard MaDI-Bench's `fullcontact` source from an empty adapter,
through both human gates, with every cycle receipted.

`flywheel.real_fullcontact.toml` selects the 1,931-record fullcontact CSV. Its
columns are anonymized to `Attribute_1..6`, so no header carries meaning and the
mapping has to be inferred from record values. That makes it the harder of the
two real splits — `forbes`' columns self-describe their target.

This run replaces an earlier one, archived in
[`../real_fullcontact_unattended/`](../real_fullcontact_unattended/README.md).
The earlier run reached the same mapping, but an operator left the session with a
gate open for 7.2 hours, so its wall-clock figures described an afternoon rather
than the loop. Every gate in this run was answered by someone at the terminal.

## What it reached

| Cycle | schema_f1 | Fields mapped that cycle |
|---|---:|---|
| 00 | `0.0000` | — (empty adapter) |
| 01 | `0.5000` | `id`, `name` |
| 02 | `0.9091` | `country`, `city`, `founded` |
| 03 | `1.0000` | `keypeople` |

Per-field yield at convergence — the share of the 1,931 records that actually
produced a value. It needs no gold and is the number to read first:

| Target | Source column | Produced | Rate |
|---|---|---:|---:|
| `id` | `Attribute_1` | 1931 / 1931 | 1.0000 |
| `name` | `Attribute_2` | 1931 / 1931 | 1.0000 |
| `country` | `Attribute_3` | 1421 / 1931 | 0.7359 |
| `city` | `Attribute_4` | 1375 / 1931 | 0.7121 |
| `keypeople` | `Attribute_5` | 192 / 1931 | 0.0994 |
| `founded` | `Attribute_6` | 1056 / 1931 | 0.5469 |

`schema_f1` finishing at `1.0000` beside a `keypeople` yield of `0.0994` is the
result worth reading. The gold scores which column maps to which target, and it
is fully satisfied. Nine records in ten still produce no `keypeople`, and the
perfect score says nothing about that.

The final gap report (`03_cycle3.gaps.txt`) contains **no `UNMAPPED_FIELD` rows
at all** — every column the source carries is mapped. What remains is a
structural bound, not unfinished work. The evaluator reports it as a number
rather than leaving it to this paragraph: `integrated_ceiling` is `0.0` with
`unsatisfiable_required` naming `assets`, `industry`, `revenue` — the required
attributes fullcontact has no column for. No cycle can move that. A `0.00` rate
under a ceiling of `0.00` means impossible; a `0.00` under a ceiling of `1.00`
would mean merely unmapped, and telling those apart is the point.
`value_recall` and `fully_correct_rate` are `null`, meaning unmeasured — the real
benchmark pins no normalized-value gold. Null is not zero.

That ceiling is a property of scoring one source against a schema describing the
*fused* company entity; see
[what `integrated_rate` is actually measuring](../../CASE_STUDY.md#what-integrated_rate-is-actually-measuring).

The `NN.evaluate.json` files below were written during the run and predate those
two fields, so they do not contain them — a receipt records what the evaluator
emitted at the time, and is not rewritten afterwards. Re-running the command under
**Reproduce** against the same committed adapter snapshot prints them.

## What it cost

| Cycle | Outcome | Wall | Agent | Gate 1 | Gate 2 |
|---|---|---:|---:|---:|---:|
| 1 | kept | 515.98s | 331.6s | 85.93s | 98.45s |
| 2 | kept | 723.41s | 544.18s | 104.9s | 74.33s |
| 3 | kept | 684.05s | 449.42s | 170.5s | 64.13s |

Derived by `scripts/cycle_log.py report` from
[`../delivery/cycles.jsonl`](../delivery/cycles.jsonl): 3 of 3 accepted at Gate 2,
0 resubmissions, 0 control stops. The agent-minutes and wall-minutes per
accepted change derived from these records are published in the README and
CASE_STUDY, and CI recomputes both from this file and fails on drift.

Zero control stops is a limit of this set, not evidence the controls are
unnecessary: no cycle attempted a protected path or regressed an onboarded field.

## What is in each cycle

`NN.adapter.toml` is the adapter as it stood after that cycle; `NN.adapter.diff`
is the change from the previous snapshot and `NN.diff_hash.txt` its
`git hash-object`; `NN.evaluate.json` is the held-out evaluator's output;
`NN.gaps.txt` is the integration gap report replayed through the live app after
the change landed.

## Reproduce

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real_fullcontact.toml
uv run python engagements/madi_onboarding/download_data.py
uv run python engagements/madi_onboarding/csv_to_ingest.py --source fullcontact
uv run python engagements/madi_onboarding/prepare_real_eval.py
uv run python engagements/madi_onboarding/evaluate.py \
  --fixtures engagements/madi_onboarding/data/madi \
  --adapters engagements/madi_onboarding/adapters_real --sources fullcontact
```

CI does not recompute these receipts the way it recomputes `runs/forbes/` and
`runs/reconcile/`: `data/madi/` is gitignored, fetched by `download_data.py`
against pinned git blob SHAs, and that download step is deliberately non-fatal so
an external outage never reds the build. The delivery figures derived from this
run *are* machine-checked — `scripts/render_delivery_table.py --check` and the
README economics check both fail CI on drift.
