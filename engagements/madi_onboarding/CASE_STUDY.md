# Case study: from accepted requests to correct company data

**Reader:** a technical reviewer assessing applied-AI delivery judgment, evaluation design, and implementation depth.

## The problem

The reference API accepts company records from several partner sources. Its canonical schema expects normalized `name`, `founded`, and `country`. Complete records also carry city, industry, assets, revenue, and key people.

`dbpedia` already works. A new `forbes` source arrives with different field names, string years, country names, and currency-formatted values. The API can accept every request while producing unusable records. The task is to improve the new source without damaging the working one.

The engagement evaluates two current correctness surfaces. It maps a source into the canonical schema, then decides which records describe the same company and how to resolve attributes that disagree. One delivery loop governs both surfaces.

## The operating boundary

The loop begins with replayed traffic and structured integration failures. An engagement-specific analyzer ranks the gaps. A human selects a bounded proposal. The implementer returns structured edits. The orchestrator validates every edit, runs tests and the evaluator, then asks a human to approve the exact tested change.

The implementer cannot write the evaluator, gold labels, fixtures, matching engine, fusion engine, or prior receipts, and cannot read the gold, the fixtures, or the receipts. Those are two separate lists enforced two separate ways: a guard inside the single write entry point, and a `PreToolUse` hook declared in the implementer's own agent definition so it binds that subagent rather than every session in the repository. It can change adapters and rules. This is a workflow control for a local harness. It is not an operating-system security boundary.

## Onboarding `forbes`

The synthetic dev split contains six `forbes` records and a working `dbpedia` source. The empty adapter is the baseline. Cycle 1 maps required fields. Cycle 2 maps optional attributes, adds `sales → revenue`, and normalizes country and money values.

| `forbes` metric | Baseline | Cycle 1 | Cycle 2 |
|---|---:|---:|---:|
| Schema-mapping F1 | 0.00 | 0.5455 | 1.00 |
| Value recall | 0.00 | 0.375 | 1.00 |
| Integrated rate | 0% | 100% | 100% |
| Fully-correct rate | 0% | 0% | 100% |
| `dbpedia` regression | — | none | none |

The [onboarding receipts](runs/MADI_EXAMPLE.md#forbes-onboarding-schema-matching--value-normalization) link the baseline, gap reports, adapter snapshots, change artifacts, hashes, and literal evaluator output. The repository ships the empty adapter so a reader can begin from the same state. The receipts preserve the converged states.

## Reconciliation

Correct ingestion exposes a different failure. The benchmark contains five gold entity pairs across sources. The seed matching rules find none. Without matched pairs, live telemetry has no fusion conflicts to report.

The evaluator can still score fusion against gold-matched clusters. Its baseline fusion accuracy is `0.875`. That is a signal for the evaluator, not a live diagnosis the analyzer can act on yet. Matching must come first.

Cycle 1 replaces exact-name matching with fuzzy, exclusive matching. Exclusive assignment prevents one record from appearing in more than one matched pair. This reaches F1 `1.00` and makes fusion conflicts visible in live telemetry. Cycle 2 uses that signal to add one per-attribute fusion rule.

| `reconcile` metric | Baseline | Cycle 1 | Cycle 2 |
|---|---:|---:|---:|
| Entity-matching F1 | 0.00 | 1.00 | 1.00 |
| Fusion accuracy | 0.875 | 0.875 | 1.00 |
| `dbpedia`/`forbes` regression | — | none | none |

The [reconciliation receipts](runs/MADI_EXAMPLE.md#reconcile-entity-matching--data-fusion) show why the cycles occur in that order. They also show the narrow change surface: matching rules in cycle 1, fusion rules in cycle 2.

## Separate real-data measurement

The synthetic dev split makes every cycle fast and reproducible. It cannot answer whether a fitted adapter transfers to a source it has not seen. The real MaDI-Bench Companies split provides that separate task.

The real `forbes` export has 2,000 records and seven raw fields with no names shared with the synthetic fixture. Its schema-mapping gold is separate. Value gold is unavailable, so value recall and fully-correct rate remain `null`; the meaningful metric is schema-mapping F1.

Five auto-gated trials started from the empty real-data adapter. Every trial converged in one cycle to schema F1 `1.00`, with no regression and two evaluator invocations per trial. The [trial report](runs/trials/README.md) records the full protocol and each result.

The current handoff uses structured `{file, old_string, new_string}` edits. `apply_edits.py` validates each target path and exact prior string before any write occurs. One bad edit rejects the whole submission. This removes diff hunk bookkeeping from the implementer’s task.

The real-data trial is a bounded result. The source mapping has low ambiguity. Five successes do not establish general agent reasoning ability, broad reliability, or production readiness.

## What the loop costs

Two human approval gates are a claim about delivery, so the loop measures itself the way it measures the app. Every cycle writes one record: wall-clock by phase, the outcome, resubmissions, submission size, evaluator invocations, and the metric deltas.

| Reported | What it answers |
|---|---|
| Agent minutes per accepted change | What the agent's own work costs, gates excluded |
| Wall minutes per accepted change | What a cycle costs end to end, gates included |
| Acceptance rate at Gate 2 | How often a proposed change survives review |
| First-pass rate | How often the first submission is the accepted one |
| Control stops | How often a guard, the evaluator, or the tests ended a cycle instead of a human |

A control firing and a human declining are recorded as different outcomes. Collapsing them would overstate reviewer workload and hide whether the controls do anything.

Two numbers are deliberately absent. **Token cost:** the harness does not expose a reliable per-subagent count, and an estimate would be the one unfalsifiable number in a document built on receipts. **Human decision time:** each gate span runs from the previous phase mark to the human's answer, so it contains the orchestrator composing the proposals or rendering the diff as well as an operator thinking, and nothing in the loop marks the boundary between them. A "human minutes" figure derived from that span would be agent time wearing a human label, so the loop reports agent time — the phases with no operator in them at all — and honest wall-clock beside it.

**Measured set: three cycles on the real `fullcontact` split.** This is the harder of the two real-data splits — `fullcontact`'s columns are anonymized (`Attribute_1`..`Attribute_6`, no header names), unlike `forbes`' self-descriptive columns, so the mapping has to come from record values, not column names. Each cycle onboarded one or more fields into the empty adapter and was reviewed at both gates:

<!-- delivery-economics:start -->
| Reported | Value |
|---|---|
| Cycles recorded / accepted at Gate 2 | 3 / 3 (100%) |
| Accepted on first pass | 100% (0 resubmissions) |
| Stopped by a control | 0 |
| Agent minutes per accepted change | 1.99 |
| Wall minutes per accepted change (incl. gates) | 4.88 |
| Evaluator calls per accepted change | not measured (`--eval-log` was not set this run) |

| Cycle | Outcome | Wall time | Agent time | Metrics moved |
|---|---|---|---|---|
| 1 | kept | 273.5s | 116.2s | `fullcontact.schema_f1` 0.0 → 0.2857 |
| 2 | kept | 186.4s | 79.2s | `fullcontact.schema_f1` 0.2857 → 0.5 |
| 3 | kept | 417.6s | 162.1s | `fullcontact.schema_f1` 0.5 → 0.9091 |
<!-- delivery-economics:end -->

Generated from [`runs/delivery/cycles.jsonl`](runs/delivery/cycles.jsonl) by `scripts/render_delivery_table.py`; CI fails if this region drifts from the committed records, so no figure here was retyped by hand.

Zero control stops is a limit of this set, not a claim the guard or the regression check are unneeded — no cycle in this run attempted a protected path or regressed an already-onboarded field. Raw records: [`engagements/madi_onboarding/runs/delivery/cycles.jsonl`](runs/delivery/cycles.jsonl).

## What the evaluator could not see

The most useful result in this run is cycle 3, and it is a failure the metric reported as a success.

Cycle 3 mapped `country`, `city`, and `founded`. `schema_f1` rose `0.50 → 0.91`, tests passed, no regression fired, and a human approved it at Gate 2. Two of those three mappings do not work on the real data:

| Mapping | Normalizer | Real value | Result |
|---|---|---|---|
| `Attribute_6 → founded` | `to_int_year` | `"1908-01-01"` | `ValueError` — the normalizer parses a bare year, not an ISO date |
| `Attribute_3 → country` | `country_to_iso` | `""` | `ValueError` on the empty values the source actually carries |
| `Attribute_4 → city` | `identity` | `"Brooklyn"` | works |

`integrated_rate` stayed at `0.00` for all three cycles and said so the whole time. `fullcontact` genuinely has no column for `industry`, `assets`, or `revenue`, so full integration was out of reach regardless — which is exactly why that zero was easy to read as a known limit instead of a live signal.

**Why the metric moved anyway.** `schema_f1` scores the *declared correspondence* between source column and target attribute. That correspondence is correct: `Attribute_6` really is the founding date. Whether any record survives normalization is a different question, and `schema_f1` does not ask it. The change was scored on the half that was right.

**The agent documented this itself and it still landed.** The implementer wrote `test_fullcontact_attribute_6_full_iso_date_is_invalid_value_format` and `test_fullcontact_attribute_3_empty_country_is_invalid_value_format` — passing tests asserting that its own mapping produces `INVALID_VALUE_FORMAT` on real input, with a comment explaining that `normalizers.py` was out of scope for the cycle. Everything needed to catch this was in the diff at Gate 2. What the reviewer saw alongside it was a rising number and a green suite.

**What this is evidence of.** Three controls behaved exactly as designed and the combination still shipped a change that improves nothing: an oracle scoring a real property that was not the property that mattered, a test suite honestly describing a non-functional result, and a human gate reading both. This is the failure mode the whole repo exists to make visible, caught by the repo's own instrumentation on its hardest task. It is not an argument that the gates are worthless — it is the measured limit of what a gate can do when the number it is shown is answering an easier question than the one being asked.

**What was built afterwards.** The evaluator now reports `field_yield`: per mapped target attribute, the share of records that actually produced a value. It was nearly free — `evaluate_source` already ran `apply_adapter` over every record and was discarding the per-field `value_normalization` failures it got back. Run against the same adapter that shipped:

| target | source | yield |
|---|---|---|
| `id`, `name`, `city` | `Attribute_1`, `_2`, `_4` | 1931 / 1931 |
| `country` | `Attribute_3` | 1200 / 1931 |
| `founded` | `Attribute_6` | 0 / 1931 |

`founded` is the known failure. `country` at 62% was not known to anyone before this metric existed — `schema_f1 = 0.91` had been reporting that mapping as simply correct.

The property that makes yield the right primary signal is that **it needs no gold**. You do not have to know the correct mapping to know that a field you just declared produced a value in zero records, which means it works on the first day of an engagement, before any answer key exists. It also now drives regression detection, where it is the only signal that functions at all on the real splits: there `fully_correct_rate` is `None`, so the pre-existing check could never fire.

Each cycle's delivery record now carries it per field, so the pairing is visible without anyone looking for it. Replaying cycle 3 through the current telemetry:

```
fullcontact.field_yield.founded   None → 0.0     delta=None
fullcontact.schema_f1              0.8 → 0.9091  delta=0.1091
```

A `null` before is "this field was not mapped at all", not "it was mapped and yielded zero" — the same distinction `value_recall` keeps on the real split, for the same reason.

Its limit is the exact mirror of `schema_f1`'s, and worth stating plainly: yield says a field produced a value, not that the value belongs there. A column mapped to the wrong target with a working normalizer yields `1.0`. The two metrics answer different halves of the question and neither replaces the other — which is the actual lesson, rather than "we fixed it."

## What this engagement demonstrates

- An integration loop can work from domain failures instead of an open-ended prompt.
- Independent evaluation can cover schema mapping, normalized values, entity matching, fusion, and source regression.
- A control pattern can carry across different change surfaces: adapters, matching rules, and fusion rules.
- The structured-edit contract removes diff hunk bookkeeping from the implementer’s task.
- A delivery loop can report its own cost per accepted change instead of asserting throughput.
- A separate data split can expose a synthetic-fixture result that fails to transfer.

## Limits

- Synthetic stages contain 6–7 records. They establish reproducibility, not scale or commercial impact.
- The real-data trial measures one low-ambiguity mapping source. It does not measure customer value or general agent capability.
- The matching implementation is fixture-scale. Production entity resolution needs blocking, operational limits, monitoring, and recovery controls.
- “Correct” means agreement with the available benchmark gold. It does not measure adoption, latency, or business value.
- A tool-call hook and a write guard enforce the documented implementer’s boundary. A user or orchestrator with broader grants can change either.
- The delivery numbers describe this operator, this hardware, and these tasks. They are a cost floor for a reviewed cycle, not an industry benchmark.

## Inspect or reproduce

Start with the [local runbook](../../SETUP.md). Read the [receipt index](runs/MADI_EXAMPLE.md) for the synthetic cycles, the [real-data baseline](runs/real_forbes/README.md) for the separate split, and the [trial report](runs/trials/README.md) for the convergence measurement.
