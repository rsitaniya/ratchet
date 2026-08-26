# Portfolio documentation design

## Objective

Make this repository a self-contained technical portfolio artifact for broad senior/principal FDE and applied-AI engineering roles. The documentation must demonstrate customer-shaped problem solving, production-minded engineering, evaluation discipline, and reusable delivery patterns without personal branding or unsupported claims.

## Audience and reader paths

| Reader | First document | Next decision |
|---|---|---|
| Hiring manager or technical reviewer | `README.md` | Is the work credible and relevant? |
| Engineer assessing implementation depth | `docs/DELIVERY_SYSTEM.md` | Is the system well designed and reusable? |
| Applied-AI/FDE reviewer | `engagements/madi_onboarding/CASE_STUDY.md` | Can this approach deliver a constrained customer-shaped outcome? |
| Practitioner | `SETUP.md`, then `docs/ADAPTING.md` | Can I run or adapt it safely? |
| Skeptical reviewer | `SECURITY.md`, then run receipts | What is enforced, measured, and out of scope? |

## Documentation architecture

### README.md — evidence-first landing page and quick-use guide

Lead with the partner-data onboarding reference engagement, not the calculator. Establish the engineering thesis and show the result, its acceptance criteria, and links to raw receipts. Retain a short verified install and run path. End with a Documentation map linking all public technical materials.

The current README will be preserved as `docs/archive/README-platform-first.md` before replacement.

### docs/DELIVERY_SYSTEM.md — reusable platform architecture

Create a platform-first companion document describing the generic delivery system: system boundary, configuration contract, runtime control flow, component responsibilities, agent and human controls, evaluator/protected-path model, test strategy, extension seams, and non-goals. This becomes the canonical location for mechanics currently repeated across README, SETUP, and the blog.

### engagements/madi_onboarding/CASE_STUDY.md — executive case study

Reframe the reference engagement as: context, objective and definition of done, constraints, delivery approach, key technical decisions, measured outcome, evidence, and honest limits. It must distinguish the synthetic fixture benchmark from a production customer deployment.

### Supporting technical documents

* `SETUP.md`: local runbook, prerequisites, installation, verified workflow, expected outcomes, and bounded troubleshooting.
* `docs/ADAPTING.md`: integration guide, prerequisites, configuration interface, validation checklist, and common failure modes.
* `SECURITY.md`: threat model, enforced boundaries, residual limits, and escalation/reporting route.
* `CHANGELOG.md`: factual project history; no architecture or portfolio narrative.
* `engagements/madi_onboarding/runs/README.md`: artifact index and reproducibility instructions; retain raw receipts unchanged.
* `DATA_LICENSE_NOTICE.md`, `LICENSE`, `NOTICE`: factual licensing only.
* `CLAUDE.md`: maintainer instructions, updated only when the public documentation map or factual-verification discipline changes.
* `docs/blog/self-shipping-api.md`: optional long-form essay; link from the README but avoid treating it as canonical reference material.

## Writing rules

* Begin each top-level document with its reader and purpose.
* Keep a claim or metric canonical in one place; use links elsewhere.
* Link every presented metric to raw evidence or a reproducing command.
* State whether evidence comes from a benchmark, local harness, or production system.
* Prefer contracts, diagrams, tables, procedures, and named trade-offs over narrative filler.
* Preserve technical terms when they identify an actual mechanism; avoid empty phrases such as "cutting-edge," "seamless," or "revolutionary."
* Do not add personal biography, social links, contact details, or implied client experience.

## Implementation sequence

1. Verify executable commands, claims, metrics, and current links before writing.
2. Archive the current README; author the evidence-first README and Documentation map.
3. Create `docs/DELIVERY_SYSTEM.md`; remove duplicated architecture explanation from supporting docs while retaining necessary local context.
4. Rewrite CASE_STUDY, SETUP, ADAPTING, SECURITY, and CHANGELOG to their bounded roles.
5. Audit all public documents for stale commands, duplicate claims, unsupported production language, broken links, and tone.
6. Validate Markdown links and run the documented commands proportionately to their risk.

## Acceptance criteria

* A reviewer can identify the problem, the technical design, the evidence, and the limits from the README in under ten minutes.
* A practitioner can follow README → SETUP to run the bundled system without needing a second document for basic setup.
* `docs/DELIVERY_SYSTEM.md` explains the generic system without using the onboarding case study as its primary explanation.
* CASE_STUDY reads as a decision record with evidence, not a product announcement.
* Every file in the public-doc inventory has one clear purpose and no factual contradiction with the code or receipts.
* The prior README remains available under `docs/archive/README-platform-first.md`.
