# Case study: partner-data onboarding

**Reader:** a reviewer assessing applied-AI delivery judgment, evaluation design, and technical execution.

## Context

A partner-data API accepts company records from sources with different field names and formats. The target schema requires normalized `name`, `founded`, and `country`; complete records also include city, industry, assets, revenue, and key people. `dbpedia` is already integrated. `forbes` arrives with renamed fields, string years, country names, and currency-formatted values.

This is a reproducible benchmark using this repository’s synthetic fixtures. The pipeline can also download the licensed MaDI-Bench Companies task; it is not a claim of production customer impact. See [data terms](DATA_LICENSE_NOTICE.md).

## Objective and constraints

| Objective | Constraint |
|---|---|
| Improve the new source’s mapping and normalized values. | The planner cannot read gold or fixtures through its Claude Code tool grants. |
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
| Value accuracy | 0.00 | 0.375 | 1.00 |
| Integrated rate | 0% | 100% | 100% |
| Fully-correct rate | 0% | 0% | 100% |
| `dbpedia` regression | — | none | none |

Every result is a [committed receipt](runs/README.md), not a dashboard claim.

## Extension: reconciliation

The same pattern covers cross-source entity matching and data fusion. Declarative matching rules improve entity-matching F1 from 0 to 1.00; per-attribute fusion rules improve fusion accuracy from 0.875 to 1.00. The matcher, fusion engine, fixtures, and oracle are protected while the rules remain the change surface.

## Limits

- Fixtures contain 6–7 records per stage; the results establish reproducibility, not scale or commercial impact.
- The matching implementation is intentionally fixture-scale; a production implementation needs blocking and operational limits appropriate to its data volume.
- “Correct” means agreement with benchmark gold. It does not substitute for user adoption, latency, or business-value measurement.
- The local permission model helps prevent evaluator contamination; it is not an OS-level security boundary.

## Reproduce

Follow the [local runbook](../../SETUP.md), then inspect the [receipt index](runs/README.md). The baseline adapter remains empty by design so the documented cycles start from the same zero state.
