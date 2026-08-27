# dev-flywheel

**A controlled delivery loop for agent-assisted integration work.**

[![CI](https://github.com/rsitaniya/dev-flywheel/actions/workflows/ci.yml/badge.svg)](https://github.com/rsitaniya/dev-flywheel/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)

A request can succeed while the integration is wrong. A source can be mapped correctly while its records still fail to match the same entities elsewhere. `dev-flywheel` turns those observed gaps into scoped, evaluated changes with two human approval gates.

The reference engagement is a partner-data API. It demonstrates one delivery loop across two decisions:

- **Onboarding:** map a new source into a canonical company schema without regressing a source that already works.
- **Reconciliation:** match entities across sources, then resolve the attribute conflicts exposed by those matches.

The implementer cannot write directly. It returns structured edits. The orchestrator checks their paths and exact prior content before it writes, then runs tests and an evaluator whose gold, fixtures, and core scoring paths are protected.

This is a local, single-operator benchmark harness. It is not an autonomous deployment product or a claim of production customer impact.

![Two reviewed onboarding cycles take a new partner source from zero mapping and value recall to a fully correct result. Every reported state has a committed evaluator receipt.](docs/madi-onboarding-demo.gif)

## Evidence at a glance

| Question | Evidence | What it establishes |
|---|---|---|
| Can a new source be onboarded without breaking an existing one? | `forbes` schema F1: `0.00 → 1.00`; value recall: `0.00 → 1.00`; no `dbpedia` regression across two recorded cycles. | The reference onboarding loop can improve a bounded adapter against held-out synthetic gold. |
| Can the same loop handle a different kind of correctness? | Entity-matching F1: `0.00 → 1.00`; fusion accuracy: `0.875 → 1.00`; no source regression across two recorded cycles. | The same controls work when the change surface moves from field mapping to matching and fusion rules. |
| Does the implementer converge on a separate real-data mapping task? | Five auto-gated trials on real MaDI-Bench Forbes data reached schema F1 `1.00` in one cycle each. | On this low-ambiguity mapping task, the implementer reached the documented target under the recorded trial protocol. |

The [receipt index](engagements/madi_onboarding/runs/MADI_EXAMPLE.md) contains every synthetic-cycle input, gap report, edit, hash, and evaluator output. The [trial report](engagements/madi_onboarding/runs/trials/README.md) contains the real-data trial protocol, failures, and limits.

## The engineering decisions

| Decision | Why it exists | Evidence and limit |
|---|---|---|
| **Signal before change** | A telemetry analyzer ranks concrete integration failures before an agent proposes work. | The two reference engagements start from replayed traffic and gap reports. An analyzer still needs domain knowledge. |
| **Structured edits, not model-authored diffs** | A read-only implementer cannot verify diff hunk bookkeeping. Exact `old_string` validation gives it a simpler, checkable handoff. | `apply_edits.py` applies all edits atomically or none. The orchestrator remains a trusted writer. |
| **Independent evaluation** | HTTP success cannot establish schema, value, matching, or fusion correctness. | Gold, fixtures, scorer, engines, and receipts sit outside the implementer’s tool grants and writable surface. Tool grants are not OS permissions. |
| **Separate real-data trial** | A fitted dev-fixture adapter may overfit aggregate score feedback. | The real MaDI configuration uses a separate adapter surface and oracle. The measured task is low-ambiguity and does not establish general agent reasoning ability. |
| **Two human gates** | Scope and final acceptance are accountable decisions. | Gate 1 approves the proposal. Gate 2 approves the exact tested result. The loop never merges or deploys itself. |

## How known failures behave

| Failure | Current response |
|---|---|
| An edit targets the evaluator, gold, fixtures, engines, or receipts | The protected-path guard rejects it before any write. |
| An edit was prepared against stale or ambiguous source text | `apply_edits.py` rejects the full submission. Every `old_string` must match exactly once. |
| A candidate improves one metric and regresses another | Gate 2 compares evaluator output with the pre-cycle baseline and blocks a regression. |
| The simulator cannot reach the API or misses its discovered behavior | CI fails on a transport exception and requires telemetry for `/ingest` and `/reconcile`. |
| The evaluator cannot represent a quality problem | The result remains unproven. The real-data trial and documented limits expose that gap; they do not conceal it. |

## Read the work at the right depth

- [Case study](engagements/madi_onboarding/CASE_STUDY.md) — the two delivery failures, the changes, the results, and the real-data trial.
- [Delivery-system architecture](docs/DELIVERY_SYSTEM.md) — contracts, decision boundaries, and implementation design.
- [Security model](SECURITY.md) — workflow controls, adversarial cases, and residual risks.
- [Run receipts](engagements/madi_onboarding/runs/MADI_EXAMPLE.md) — raw reproducible evidence for onboarding and reconciliation.
- [Real-data baseline](engagements/madi_onboarding/runs/real_forbes/README.md) and [convergence trials](engagements/madi_onboarding/runs/trials/README.md) — separate test-split evidence.
- [Local runbook](SETUP.md) — install and reproduce the reference engagement.
- [Adaptation guide](docs/ADAPTING.md) — configure the generic loop for another FastAPI API.
- [Data license notice](engagements/madi_onboarding/DATA_LICENSE_NOTICE.md) — boundaries for the external benchmark data.

## Run the reference engagement

Requires Python 3.11–3.13 and [uv](https://pypi.org/project/uv/).

```bash
uv sync --all-extras --locked
uv run pytest tests/ -q
uv run ruff check .
```

To replay the onboarding baseline, follow the two-terminal procedure in [SETUP.md](SETUP.md). The shipped `forbes` adapter is intentionally empty. The recorded successful states are receipts, so a reader can begin from the same baseline.

## Boundaries

- The synthetic fixtures contain 6–7 records per stage. They show reproducibility, not scale.
- The real-data trial measures one source mapping. It does not establish customer impact, production throughput, tenant isolation, or broad agent capability.
- `/reconcile` is fixture-scale. Production entity resolution needs blocking, resource limits, monitoring, and recovery controls.
- The local permission model constrains the documented implementer. It does not create an operating-system security boundary.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
