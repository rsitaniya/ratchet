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

Replace the current README in place; do not archive the previous version. Create and use a MaDI onboarding demo asset in the evidence-led opening. The existing calculator-loop `docs/demo.gif` may remain in the repository as a supporting artifact, but will move out of the README's primary narrative unless it directly supports the generic-system section.

### docs/DELIVERY_SYSTEM.md — reusable platform architecture

Create a platform-first companion document describing the generic delivery system: system boundary, configuration contract, runtime control flow, component responsibilities, agent and human controls, evaluator/protected-path model, test strategy, extension seams, and non-goals. This becomes the canonical location for mechanics currently repeated across README, SETUP, and the blog.

### engagements/madi_onboarding/CASE_STUDY.md — executive case study

Reframe the reference engagement as: context, objective and definition of done, constraints, delivery approach, key technical decisions, measured outcome, evidence, and honest limits. It must distinguish the synthetic fixture benchmark from a production customer deployment.

### Supporting technical documents

* `SETUP.md`: local runbook, prerequisites, installation, verified workflow, expected outcomes, and bounded troubleshooting.
* `docs/ADAPTING.md`: integration guide, prerequisites, configuration interface, validation checklist, and common failure modes.
* `SECURITY.md`: threat model, enforced boundaries, residual limits, and escalation/reporting route.
* `CHANGELOG.md`: preserve committed entries as append-only project history. New entries stay factual and concise; they may retain load-bearing rationale when it explains a behavioral change.
* `engagements/madi_onboarding/runs/README.md`: artifact index and reproducibility instructions; retain raw receipts unchanged.
* `engagements/madi_onboarding/DATA_LICENSE_NOTICE.md`, `LICENSE`, `NOTICE`: factual licensing only.
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

1. Verify executable commands, claims, metrics, current links, and the available evidence required for the MaDI demo.
2. Create `docs/DELIVERY_SYSTEM.md` with its complete structure and canonical mechanics before writing documents that link to it.
3. Create a MaDI onboarding demo asset; verify that every frame is traceable to a committed receipt or reproducible command.
4. Replace `README.md` with the evidence-first landing page, short quick-use guide, and final Documentation map.
5. Rewrite CASE_STUDY, SETUP, ADAPTING, SECURITY, and the engagement-scoped data-license notice to their bounded roles; preserve existing changelog entries, editing only when a verified factual correction is necessary.
6. Audit all public documents for stale commands, duplicate claims, unsupported production language, broken links, tone, and accurate placement of the calculator demo.
7. Validate Markdown links, demo references, and documented commands proportionately to their risk.

## Acceptance criteria

* A reviewer can identify the problem, the technical design, the evidence, and the limits from the README in under ten minutes.
* A practitioner can follow README → SETUP to run the bundled system without needing a second document for basic setup.
* `docs/DELIVERY_SYSTEM.md` explains the generic system without using the onboarding case study as its primary explanation.
* CASE_STUDY reads as a decision record with evidence, not a product announcement.
* Every file in the public-doc inventory has one clear purpose and no factual contradiction with the code or receipts.
* The README is replaced in place and links to every primary public document in its final Documentation map.
* The MaDI demo is evidence-led: all screens show committed or reproducible behavior, and no screen implies a production customer deployment.
