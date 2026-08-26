# Case study: partner-data onboarding

**Reader:** a reviewer assessing applied-AI delivery judgment, evaluation design, and technical execution.

## Context

A partner-data API accepts company records from sources with different field names and formats. The target schema requires normalized `name`, `founded`, and `country`; complete records also include city, industry, assets, revenue, and key people. `dbpedia` is already integrated. `forbes` arrives with renamed fields, string years, country names, and currency-formatted values.

This is a reproducible benchmark using this repository's synthetic fixtures — not a claim of production customer impact. Those synthetic fixtures are the **dev** split: fast, deterministic, scored every cycle at Gate 2. The same loop also runs against the real MaDI-Bench Companies task as a **test** split (`flywheel.real.toml`, `data/madi/`): `download_data.py` fetches the pinned, checksum-verified CSVs, `csv_to_ingest.py` and `prepare_real_eval.py` convert them and the benchmark's own schema-matching gold into the shape `evaluate.py` already reads, and it is scored **once**, offline, never during a loop cycle — see [Extension: the real-data test split](#extension-the-real-data-test-split) below. See [data terms](DATA_LICENSE_NOTICE.md) — the data's own license is not stated by its authors.

## Objective and constraints

| Objective | Constraint |
|---|---|
| Improve the new source’s mapping and normalized values. | The implementer subagent cannot read gold, fixtures, or `runs/` receipts through its Claude Code tool grants (`Read, Grep, Glob` only, no Bash). |
| Keep the seed source correct. | Gate 2 compares evaluator output with a pre-cycle baseline. |
| Make each decision auditable. | A cycle produces ranked gaps, an adapter diff, a hash, and evaluator JSON. |
| Keep ordinary changes narrow. | Adapters and rules are writable; evaluator, gold, fixtures, and engines are protected. |

## Delivery approach

1. Replay `forbes` records through `POST /ingest`.
2. Rank structured `UNMAPPED_FIELD`, format, and required-field gaps by affected records.
3. Approve one bounded adapter change.
4. Validate the diff, run the evaluator against held-out truth, and approve or revert the tested result.

The first cycle maps required fields and reaches 6/6 integrated records. The second maps optional attributes, adds the semantic rename `sales → revenue`, and normalizes money and country values.

## Measured outcome

| `forbes` metric | Baseline | Cycle 1 | Cycle 2 |
|---|---:|---:|---:|
| Schema-mapping F1 | 0.00 | 0.5455 | 1.00 |
| Value recall | 0.00 | 0.375 | 1.00 |
| Integrated rate | 0% | 100% | 100% |
| Fully-correct rate | 0% | 0% | 100% |
| `dbpedia` regression | — | none | none |

Every result is a [committed receipt](runs/MADI_EXAMPLE.md), not a dashboard claim.

## Extension: reconciliation

The same pattern covers cross-source entity matching and data fusion, with its own two-cycle
receipt trail. Cycle 1 replaces the seed's exact-name match with fuzzy matching, which alone
recovers every gold pair. That match is what makes fusion conflicts visible in live telemetry at
all — matching.py's assignment is exclusive (one entity, not one-to-many), so a matched pair's
attribute disagreements only show up once matching works. Cycle 2 reads that live signal and adds
one per-attribute fusion override.

| `reconcile` metric | Baseline | Cycle 1 | Cycle 2 |
|---|---:|---:|---:|
| Entity-matching F1 | [0.00](runs/reconcile/00_baseline.evaluate.json) | [1.00](runs/reconcile/01_cycle1.evaluate.json) | [1.00](runs/reconcile/02_cycle2.evaluate.json) |
| Fusion accuracy | [0.875](runs/reconcile/00_baseline.evaluate.json) | [0.875](runs/reconcile/01_cycle1.evaluate.json) | [1.00](runs/reconcile/02_cycle2.evaluate.json) |
| `dbpedia`/`forbes` regression | — | none | none |

The matcher, fusion engine, fixtures, and oracle are protected; `matching_rules.toml` and
`fusion_rules.toml` are the change surface. Receipts: [runs/reconcile](runs/reconcile/).

## Extension: the real-data test split

The synthetic fixtures above are the loop's **dev** split — fast, deterministic, scored every
cycle. MaDI-Bench's own forbes/dbpedia/fullcontact CSVs (2000/10085/1931 records) and its own
`sm_mapping_gold.json` are the **test** split, scored once, offline, selected by
`FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real.toml` against a separate
`adapters_real/` write surface. Real forbes columns (`forbes_url, company, url, region,
business_segment, asset_value, sales_figure`) share nothing with the synthetic ones, so this is a
genuine held-out distribution, not a subsample: the synthetic adapter cannot transfer. Only the
schema-matching gold is pinned for the real benchmark, so `value_recall` and `fully_correct_rate`
report `null` there, never `0.0` — see `evaluate.py`.

| `forbes` (real, 2000 records) | Baseline |
|---|---:|
| Schema-mapping F1 | [0.00](runs/real_forbes/00_baseline.evaluate.json) |
| Integrated rate | [0.0%](runs/real_forbes/00_baseline.evaluate.json) |
| Value recall / fully-correct rate | null (no value gold pinned) |

This is the same empty-adapter starting point as the synthetic baseline above — not yet a
converged result. Measuring how reliably the agent converges it (cycles to converge, failure
modes, across repeated runs) is `/dev-loop-trial`'s job; see `runs/trials/README.md` once trials
have been run.

## Limits

- Fixtures contain 6–7 records per stage; the results establish reproducibility, not scale or commercial impact.
- The matching implementation is intentionally fixture-scale; a production implementation needs blocking and operational limits appropriate to its data volume.
- “Correct” means agreement with benchmark gold. It does not substitute for user adoption, latency, or business-value measurement.
- Claude Code deny rules block this repo's own implementer subagent from reading fixtures, gold, and `runs/` receipts at the tool layer; that is not an OS-level filesystem permission, and changing tool grants changes the boundary.

## Reproduce

Follow the [local runbook](../../SETUP.md), then inspect the [receipt index](runs/MADI_EXAMPLE.md). The baseline adapter remains empty by design so the documented cycles start from the same zero state.
