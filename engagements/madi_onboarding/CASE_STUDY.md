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

Two human approval gates are a claim about delivery, so the loop measures itself the way it measures the app. Every cycle writes one record: wall-clock by phase, human seconds at each gate, the outcome, resubmissions, submission size, evaluator invocations, and the metric deltas.

| Reported | What it answers |
|---|---|
| Human minutes per accepted change | What the two gates actually cost the reviewer |
| Wall minutes per accepted change | What a cycle costs end to end |
| Acceptance rate at Gate 2 | How often a proposed change survives review |
| First-pass rate | How often the first submission is the accepted one |
| Control stops | How often a guard, the evaluator, or the tests ended a cycle instead of a human |

A control firing and a human declining are recorded as different outcomes. Collapsing them would overstate reviewer workload and hide whether the controls do anything.

Token cost is not reported. The harness does not expose a reliable per-subagent count, and an estimate would be the one unfalsifiable number in a document built on receipts.

Numbers pending: the recorder is wired into both loop modes, and this section reports measured cycles once a measured set has been run.

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
