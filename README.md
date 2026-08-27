# dev-flywheel

**A controlled delivery loop for agent-assisted integration work.**

[![CI](https://github.com/rsitaniya/dev-flywheel/actions/workflows/ci.yml/badge.svg)](https://github.com/rsitaniya/dev-flywheel/actions/workflows/ci.yml)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)

A request can succeed while the integration is wrong. A source can be mapped correctly while its records still fail to match the same entities elsewhere. `dev-flywheel` turns those observed gaps into scoped, evaluated changes with two human approval gates.

The reference engagement is a partner-data API. It demonstrates one delivery loop across two decisions:

- **Onboarding:** map a new source into a canonical company schema without regressing a source that already works.
- **Reconciliation:** match entities across sources, then resolve the attribute conflicts exposed by those matches.

The implementer cannot write directly. It returns structured edits. The orchestrator checks their paths and exact prior content before it writes, then runs tests and an evaluator whose gold, fixtures, and core scoring paths are protected. Every cycle records what it cost, so the delivery claim is a number rather than an adjective.

This is a local, single-operator benchmark harness. It is not an autonomous deployment product or a claim of production customer impact.

![Two reviewed onboarding cycles take a new partner source from zero mapping and value recall to a fully correct result. Every reported state has a committed evaluator receipt.](docs/madi-onboarding-demo.gif)

## Evidence at a glance

| Question | Evidence | What it establishes |
|---|---|---|
| Can a new source be onboarded without breaking an existing one? | `forbes` schema F1: `0.00 → 1.00`; value recall: `0.00 → 1.00`; no `dbpedia` regression across two recorded cycles. | The reference onboarding loop can improve a bounded adapter against held-out synthetic gold. |
| Can the same loop handle a different kind of correctness? | Entity-matching F1: `0.00 → 1.00`; fusion accuracy: `0.875 → 1.00`; no source regression across two recorded cycles. | The same controls work when the change surface moves from field mapping to matching and fusion rules. |
| **Does it hold up on real data where the answer is genuinely ambiguous?** *(the strongest evidence here)* | Three human-gated cycles on the real `fullcontact` split — 1,931 real MaDI-Bench records, columns anonymized to `Attribute_1..6` so the mapping must come from record values: `schema_f1` `0.00 → 0.29 → 0.50 → 0.91`, `1.99` agent minutes and `4.88` wall minutes per accepted change, `100%` first-pass acceptance, `0` control stops. Every cycle is a committed record in [`cycles.jsonl`](engagements/madi_onboarding/runs/delivery/cycles.jsonl), and CI recomputes these numbers from it. | This is the hardest task in the repo and the only real-data run that is both human-gated and receipted, so it carries more weight than the convergence trials below. No guard or regression fired in this set — a limit of the measurement, not a claim the controls are unnecessary. Evaluator-call counts were not tracked in this run (`--eval-log` was not set) and are reported as not measured rather than zero. Cycle 3 is the informative one: read [what the evaluator could not see](engagements/madi_onboarding/CASE_STUDY.md#what-the-evaluator-could-not-see). |
| Does the implementer converge from an empty adapter, repeatably? | Five auto-gated trials on real MaDI-Bench Forbes data reached schema F1 `1.00` in one cycle each. | Weaker evidence than the row above, deliberately. Both gates were auto-answered and every run was reverted afterwards, so these are measurement runs with no receipts to commit — and Forbes' columns self-describe, so the task is low-ambiguity. It shows repeatability of the mechanics, not that a reviewed cycle produces a correct result. |

The [receipt index](engagements/madi_onboarding/runs/MADI_EXAMPLE.md) contains every synthetic-cycle input, gap report, edit, hash, and evaluator output. The [trial report](engagements/madi_onboarding/runs/trials/README.md) contains the real-data trial protocol, failures, and limits.

## The engineering decisions

| Decision | Why it exists | Evidence and limit |
|---|---|---|
| **Signal before change** | A telemetry analyzer ranks concrete integration failures before an agent proposes work. | The two reference engagements start from replayed traffic and gap reports. An analyzer still needs domain knowledge. |
| **Structured edits, not model-authored diffs** | A read-only implementer cannot verify diff hunk bookkeeping. Exact `old_string` validation gives it a simpler, checkable handoff. | `apply_edits.py` applies all edits atomically or none. The orchestrator remains a trusted writer. |
| **Independent evaluation** | HTTP success cannot establish schema, value, matching, or fusion correctness. | Gold, fixtures, and receipts are unreadable to the implementer; the scorer and engines are unwritable. Both are tool-call controls, not OS permissions. |
| **Separate real-data trial** | A fitted dev-fixture adapter may overfit aggregate score feedback. | The real MaDI configuration uses a separate adapter surface and oracle. The measured task is low-ambiguity and does not establish general agent reasoning ability. |
| **Two human gates** | Scope and final acceptance are accountable decisions. | Gate 1 approves the proposal. Gate 2 approves the exact tested result. The loop never merges or deploys itself. |
| **Boundaries scoped to the agent they bind** | A read boundary enforced session-wide also blocks the orchestrator from receipts it needs at Gate 2. | The implementer's read deny is a `PreToolUse` hook in its own agent definition. Gold and fixtures stay denied repository-wide; `runs/` does not. |
| **The loop measures itself** | Two approval gates are a throughput claim, and a throughput claim needs a number. | Per-cycle delivery records give agent time and wall time per accepted change, and CI recomputes both from the committed records. Two numbers are not claimed: token cost (no reliable per-subagent count exists) and human decision time (the gate spans contain orchestrator work too, and nothing marks the boundary). |

## How known failures behave

| Failure | Current response |
|---|---|
| An edit targets the evaluator, gold, fixtures, engines, or receipts | The protected-path guard rejects it before any write. |
| The implementer tries to read gold, fixtures, or a prior receipt | The agent-scoped read hook denies the call, including a grep aimed at a parent directory and a grep that names no path at all, and denies everything if no configuration resolves. |
| An edit was prepared against stale or ambiguous source text | `apply_edits.py` rejects the full submission. Every `old_string` must match exactly once. |
| A candidate improves one metric and regresses another | Gate 2 compares evaluator output with the pre-cycle baseline and blocks a regression. |
| The simulator cannot reach the API or misses its discovered behavior | CI fails on a transport exception and requires telemetry for `/ingest` and `/reconcile`. |
| The evaluator cannot represent a quality problem | Nothing stops it, and this has actually happened here. On the hardest real split a change raised `schema_f1` while normalizing zero real records; tests, the regression check, and a human gate all passed it. The evaluator now also reports `field_yield` — per mapped attribute, the share of records that produced a value — which needs no gold and exposed a second field silently failing on 38% of records. Written up in [what the evaluator could not see](engagements/madi_onboarding/CASE_STUDY.md#what-the-evaluator-could-not-see), including what yield still cannot see. |

## Read the work at the right depth

- [Case study](engagements/madi_onboarding/CASE_STUDY.md) — the two delivery failures, the changes, the results, and the real-data trial.
- [Delivery-system architecture](docs/DELIVERY_SYSTEM.md) — contracts, decision boundaries, and implementation design.
- [Security model](SECURITY.md) — workflow controls, adversarial cases, and residual risks.
- [Run receipts](engagements/madi_onboarding/runs/MADI_EXAMPLE.md) — raw reproducible evidence for onboarding and reconciliation.
- [Real-data baseline](engagements/madi_onboarding/runs/real_forbes/README.md) and [convergence trials](engagements/madi_onboarding/runs/trials/README.md) — separate test-split evidence.
- [Delivery cost](engagements/madi_onboarding/CASE_STUDY.md#what-the-loop-costs) — what a reviewed cycle takes in human and wall time.
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

- Scale differs sharply by split, and only the smallest is synthetic. The synthetic fixtures used every dev cycle contain 6–7 records per stage and show reproducibility, not scale. The real splits are the benchmark's own data: `fullcontact` scores 1,931 records and real `forbes` scores 2,000. None of that is production volume, but the real-data claims above are not fixture-scale claims.
- The real-data runs measure single-source schema mapping. They do not establish customer impact, production throughput, tenant isolation, or broad agent capability.
- `/reconcile` is fixture-scale. Production entity resolution needs blocking, resource limits, monitoring, and recovery controls.
- The local permission model constrains the documented implementer. It does not create an operating-system security boundary.
- Delivery numbers describe one operator on one machine across these tasks. They are a cost floor for a reviewed cycle, not a benchmark.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
