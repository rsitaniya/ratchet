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

**Measured set: three cycles on the real `fullcontact` split.** This is the harder of the two real-data splits — `fullcontact`'s columns are anonymized (`Attribute_1`..`Attribute_6`, no header names), unlike `forbes`' self-descriptive columns, so the mapping has to come from record values, not column names. Each cycle onboarded one or more fields into the empty adapter and was reviewed at both gates: cycle 1 mapped `id` and `name`, cycle 2 `country`, `city` and `founded`, cycle 3 `keypeople`. Every gate in this set was answered by an operator at the terminal, which is what makes the wall-clock column usable. It replaces an earlier run of the same split whose numbers were not — that run's receipts and the reason it was superseded are in [`runs/real_fullcontact_unattended/`](runs/real_fullcontact_unattended/README.md), and its own findings are discussed in the next section. Per-cycle receipts for this run are in [`runs/real_fullcontact/`](runs/real_fullcontact/README.md).

<!-- delivery-economics:start -->
| Reported | Value |
|---|---|
| Cycles recorded / accepted at Gate 2 | 3 / 3 (100%) |
| Accepted on first pass | 100% (0 resubmissions) |
| Stopped by a control | 0 |
| Agent minutes per accepted change | 7.36 |
| Wall minutes per accepted change (incl. gates) | 10.69 |
| Evaluator calls per accepted change | not measured (`--eval-log` was not set this run) |

| Cycle | Outcome | Wall time | Agent time | Metrics moved |
|---|---|---|---|---|
| 1 | kept | 516.0s | 331.6s | `fullcontact.field_yield.id` new → 1.0, `fullcontact.field_yield.name` new → 1.0, `fullcontact.schema_f1` 0.0 → 0.5 |
| 2 | kept | 723.4s | 544.2s | `fullcontact.field_yield.city` new → 0.7121, `fullcontact.field_yield.country` new → 0.7359, `fullcontact.field_yield.founded` new → 0.5469, `fullcontact.schema_f1` 0.5 → 0.9091 |
| 3 | kept | 684.0s | 449.4s | `fullcontact.field_yield.keypeople` new → 0.0994, `fullcontact.schema_f1` 0.9091 → 1.0 |
<!-- delivery-economics:end -->

Generated from [`runs/delivery/cycles.jsonl`](runs/delivery/cycles.jsonl) by `scripts/render_delivery_table.py`; CI fails if this region drifts from the committed records, so no figure here was retyped by hand.

Zero control stops is a limit of this set, not a claim the guard or the regression check are unneeded — no cycle in this run attempted a protected path or regressed an already-onboarded field. Raw records: [`engagements/madi_onboarding/runs/delivery/cycles.jsonl`](runs/delivery/cycles.jsonl).

The gap between the two time figures is small here — `7.36` agent minutes against `10.69` wall minutes — because the three cycles closed within 168 seconds of each other end to end (516s, 723s, 684s) and no gate span exceeded 171 seconds. That is the point of measuring them separately. An earlier run of this same split reported `156.06` wall minutes per accepted change on the same work, because one Gate 2 span ran 25,996 seconds with nobody at the terminal. Neither figure was trimmed; the loop cannot tell an operator thinking from an operator absent, so it publishes what it measured and says which run each number came from.

## What the evaluator could not see

The most useful result on this split came from the first run of it, and it is a failure the metric reported as a success. That run's delivery receipts were reset so the split could be re-measured under the contract it motivated, but its commits remain the record: `8e00e52` mapped the three fields, and `5e21205` added the per-field verification requirement in response. The split has since been re-measured twice from an empty adapter — the table above is the second — and the intermediate run's receipts are reconstructed in [`runs/real_fullcontact_unattended/`](runs/real_fullcontact_unattended/README.md).

That run's third cycle mapped `country`, `city`, and `founded`. `schema_f1` rose `0.50 → 0.91`, tests passed, no regression fired, and a human approved it at Gate 2. Two of those three mappings do not work on the real data:

| Mapping | Normalizer | Real value | Result |
|---|---|---|---|
| `Attribute_6 → founded` | `to_int_year` | `"1908-01-01"` | `ValueError` — the normalizer parses a bare year, not an ISO date |
| `Attribute_3 → country` | `country_to_iso` | `""` | `ValueError` on the empty values the source actually carries |
| `Attribute_4 → city` | `identity` | `"Brooklyn"` | works |

`integrated_rate` stayed at `0.00` in that run and in this one, and said so the whole time. `fullcontact` genuinely has no column for `industry`, `assets`, or `revenue`, so full integration was out of reach regardless — which is exactly why that zero was easy to read as a known limit instead of a live signal.

**Why the metric moved anyway.** `schema_f1` scores the *declared correspondence* between source column and target attribute. That correspondence is correct: `Attribute_6` really is the founding date. Whether any record survives normalization is a different question, and `schema_f1` does not ask it. The change was scored on the half that was right.

**The agent documented this itself and it still landed.** The implementer wrote `test_fullcontact_attribute_6_full_iso_date_is_invalid_value_format` and `test_fullcontact_attribute_3_empty_country_is_invalid_value_format` — passing tests asserting that its own mapping produces `INVALID_VALUE_FORMAT` on real input, with a comment explaining that `normalizers.py` was out of scope for the cycle. Everything needed to catch this was in the diff at Gate 2. What the reviewer saw alongside it was a rising number and a green suite.

**What this is evidence of.** Three controls behaved exactly as designed and the combination still shipped a change that improves nothing: an oracle scoring a real property that was not the property that mattered, a test suite honestly describing a non-functional result, and a human gate reading both. This is the failure mode the whole repo exists to make visible, caught by the repo's own instrumentation on its hardest task. It is not an argument that the gates are worthless — it is the measured limit of what a gate can do when the number it is shown is answering an easier question than the one being asked.

**What was built afterwards.** The evaluator now reports `field_yield`: per mapped target attribute, the share of records that actually produced a value. It was nearly free — `evaluate_source` already ran `apply_adapter` over every record and was discarding the per-field `value_normalization` failures it got back. Run against the adapter that shipped in `8e00e52`:

| target | source | yield |
|---|---|---|
| `id`, `name`, `city` | `Attribute_1`, `_2`, `_4` | 1931 / 1931 |
| `country` | `Attribute_3` | 1200 / 1931 |
| `founded` | `Attribute_6` | 0 / 1931 |

`founded` is the known failure. `country` at 62% was not known to anyone before this metric existed — `schema_f1 = 0.91` had been reporting that mapping as simply correct.

The property that makes yield the right primary signal is that **it needs no gold**. You do not have to know the correct mapping to know that a field you just declared produced a value in zero records, which means it works on the first day of an engagement, before any answer key exists. It also now drives regression detection, where it is the only signal that functions at all on the real splits: there `fully_correct_rate` is `None`, so the pre-existing check could never fire.

Each cycle's delivery record now carries it per field, so the pairing is visible without anyone looking for it. Replaying that cycle through the current telemetry:

```
fullcontact.field_yield.founded   None → 0.0     delta=None
fullcontact.schema_f1              0.8 → 0.9091  delta=0.1091
```

A `null` before is "this field was not mapped at all", not "it was mapped and yielded zero" — the same distinction `value_recall` keeps on the real split, for the same reason.

Its limit is the exact mirror of `schema_f1`'s, and worth stating plainly: yield says a field produced a value, not that the value belongs there. A column mapped to the wrong target with a working normalizer yields `1.0`. The two metrics answer different halves of the question and neither replaces the other — which is the actual lesson, rather than "we fixed it."

**What the re-runs measured.** The three cycles in the table above redid the split from the same empty adapter. Cycle 2 mapped the same three fields as `8e00e52` and reached the same `schema_f1` of `0.9091` — with `founded` at `1056 / 1931` instead of `0`, and `country` at `1421 / 1931` instead of `1200`. Both re-measurements produced identical yields on all six fields from independently re-derived normalizers and country tables, which is reproducibility evidence rather than a second capability claim. The difference is not a better model. A submission now has to carry a per-field trace of a real source value through its chosen normalizer, and a row whose result is an error is rejected before the tests run, so a mapping that normalizes nothing cannot be submitted without the agent writing down that it is dead. `founded` needed a new `iso_date_to_year` normalizer to land at all; `city` needed one that rejects `""` and the literal `"null"`, because `identity` would have reported `1.00` for a column that delivers a value in 71% of records.

Final yields, each at the ceiling its source imposes:

| target | source | yield | what caps it |
|---|---|---|---|
| `id`, `name` | `Attribute_1`, `_2` | 1931 / 1931 | nothing — always present |
| `country` | `Attribute_3` | 1421 / 1931 | 508 empty, 2 `"Other"` |
| `city` | `Attribute_4` | 1375 / 1931 | 464 empty, 92 literal `"null"` |
| `founded` | `Attribute_6` | 1056 / 1931 | 875 empty |
| `keypeople` | `Attribute_5` | 192 / 1931 | 1739 empty |

`schema_f1` finished at `1.00` beside an `integrated_rate` of `0.00`. That pairing is the whole point: every column is now mapped to the attribute the answer key says it belongs to, and not one record onboards, because `fullcontact` carries no `industry`, `assets`, or `revenue` column at all. A complete mapping and a usable dataset are different things, and only one of the two metrics can tell them apart.

## What `integrated_rate` is actually measuring

`schema_f1` reaching `1.00` beside an `integrated_rate` of `0.00` invites an obvious
question: is the second number broken? It is computed correctly, but it was scoped
wrongly, and saying so precisely matters more than the number.

MaDI's target schema marks 8 of its 9 attributes required, and
`prepare_real_eval.py` copies that list verbatim — it is the benchmark's list, not
this engagement's. What the schema describes, though, is the **fused** company
entity. Its own field descriptions say so: `assets`, `revenue` and `keypeople` each
read *"For fusion evaluation this value uses 2016 as the task-level temporal
target."* The three sources are complementary by construction:

| Source | Supplies | Structurally missing |
|---|---|---|
| `dbpedia` | all 8 required, plus `keypeople` | — |
| `forbes` | id, name, country, industry, assets, revenue | `founded`, `city` |
| `fullcontact` | id, name, country, city, founded, keypeople | `industry`, `assets`, `revenue` |

`fullcontact` supplies exactly what `forbes` lacks. Scoring either alone against a
fused-entity bar returns a constant fixed by its column list — not a result, and
not something any cycle can move. Reported bare across three cycles, `0.00 → 0.00`
reads as background noise, which is how a live signal got ignored once already.

**So the bound is computed now, not narrated.** `evaluate_source` reports
`integrated_ceiling` — the best `integrated_rate` a perfect set of normalizers could
reach — and `unsatisfiable_required`, the required attributes gold says this source
has no column for. Neither needs value gold, so both work on the real splits, the
same property that makes `field_yield` usable there. It replaces a sentence four
documents and the Gate 2 instructions each maintained by hand.

The distinction it recovers is load-bearing in both directions:

| Source | `integrated_rate` | `integrated_ceiling` | `unsatisfiable_required` |
|---|---:|---:|---|
| `forbes` (synthetic, empty adapter) | 0.00 | **1.00** | — |
| `dbpedia` (synthetic, converged) | 1.00 | 1.00 | — |
| `fullcontact` (real) | 0.00 | **0.00** | `assets`, `industry`, `revenue` |
| `forbes` (real) | 0.00 | **0.00** | `city`, `founded` |
| `dbpedia` (real) | 0.00 | **0.0413** | — |

The first and third rows were indistinguishable before: both `0.00`, one meaning
"not mapped yet", the other "cannot ever be". The last row is the one nobody knew.
`dbpedia` is the only real source carrying a column for every required attribute,
so it is structurally capable — and still only **4.13%** of its records hold a
usable value for all eight at once. Even the richest real source is 96% incomplete
at the record level, which is a fact about the benchmark that no metric here
previously reported.

**What this harness does not yet evaluate.** The fused entity is the thing MaDI's
required list describes, and completeness is a cross-source property: a company
complete in neither `forbes` nor `fullcontact` may well be complete once the two are
matched and fused. This harness does not measure that on real data today.
`download_data.py` pins Stage 1 only — the three CSVs, the target schema, and the
schema-matching gold — and `evaluate_reconcile` scores matching and fusion against
the synthetic `reconcile` fixtures alone, so the real-split evaluator emits no
`reconcile` key at all. Until it does, `integrated_rate` on a real split should be
read as an ingest-stage coverage number with a stated ceiling, never as an
integration score.

That is a limit of what this harness pins, **not** a limit of the benchmark. An
earlier version of this paragraph claimed no entity-matching or fusion gold was
published for the real sources, and that was wrong — the claim was inferred from
`download_data.py`'s manifest instead of checked against MaDI-Bench, and it shipped.
Both golds exist upstream under `use cases/companies/base/input/`:
`entitymatching/forbes_2_{fullcontact,dbpedia}_{all,train,val,test}.csv` carries
labelled record pairs (`left_id,right_id,label`), and `fusion/{test,validation}_set.xml`
carries hand-annotated fused records, with a `*_better_readability.csv` view whose
columns are exactly the target schema. The pair ids are ones this loop already
produces — `fullcontact_467` is `Attribute_1`, mapped to `id` in cycle 1. Scoring
real matching and fusion is therefore available work, not an impossibility, and it is
the route by which fused completeness becomes measurable.

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
