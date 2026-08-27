# Writing a canonical project post

Use this guide when a portfolio repository needs a canonical article on `sitaniya.com` or a similar personal site. The article gives an engineering leader enough context to assess the work. The repository remains the runnable artifact and source of detailed proof.

## Reader and outcome

Write for a technical leader, principal engineer, staff-plus peer, or hiring manager who is deciding whether the project demonstrates sound delivery judgment.

Before drafting, write one sentence for each:

| Question | Required answer |
|---|---|
| What engineering judgment should the reader retain? | One specific decision, boundary, or trade-off. |
| What concrete evidence supports it? | Files, receipts, test output, benchmark data, or a reproducible command. |
| What can this project establish? | The narrow result supported by the evidence. |
| Where does that evidence stop? | Scale, security, data, operational, or product limitations. |
| What should an interested reader do next? | Inspect a receipt, read a technical doc, or run a short command path. |

If the first answer contains more than one governing idea, narrow it. A launch post needs a center of gravity.

## Claim ledger

Build a claim ledger before prose. It prevents the post from becoming a repository tour or a list of components.

| Claim | Evidence | Exact location | Limit or qualification |
|---|---|---|---|
| The evaluator catches schema and value regressions | Evaluator JSON and test | `runs/.../*.evaluate.json`, test path | Covers configured benchmark metrics only. |
| A cycle improved the Forbes adapter | Baseline and cycle receipts | Receipt index | Synthetic fixtures; six records per stage. |

Every material statement must have a row. Delete claims whose evidence cannot be named. State the boundary where a strong reader would ask for one.

Numbers need their unit, population, and comparator. “Value recall reached 1.00 against held-out gold after cycle 2” is inspectable. “The agent achieved perfect accuracy” leaves too much unstated.

## Article shape

Use this order unless the project’s evidence calls for a different sequence.

1. **Operational tension.** Open with a concrete failure mode, incident pattern, or delivery decision. Give the reader a reason the work exists.
2. **Engineering judgment.** State the governing idea in plain language. Tie it to the consequence that matters in practice.
3. **Mechanism.** Describe only the moving parts needed to understand the judgment. Lead with boundaries and handoffs, then name tools if they help.
4. **Evidence.** Present the smallest set of results that prove the claim. Link raw artifacts close to the result.
5. **Limits.** Name the important unproven cases. Explain what additional work would be required to cover them.
6. **Runnable next step.** Give an exact, short route into the artifact. Use the repository’s current install and run commands. Link deeper setup separately.

The opening and conclusion should work for someone who never runs the code. The body should reward someone who does.

## Evidence choices

Prefer evidence with a stable public path:

- committed evaluator output, benchmark receipts, fixtures, and diffs;
- test names that express an invariant;
- a small trace that shows inputs, decision, change, and verification;
- an architecture document where contracts and control boundaries are explicit;
- a command a reader can copy without filling in hidden environment details.

Link a receipt for every headline metric. Link technical documentation for implementation detail. Avoid copying large tables, setup guides, or architecture diagrams into the article when the repository already carries them.

Keep repository state and post state aligned. Check every command, metric, file path, benchmark label, and non-goal against the release branch immediately before publishing.

## Prose

Write with declarative sentences. Give subjects and verbs to the system under discussion. Name the actor that proposes, modifies, evaluates, approves, or operates.

Use concrete nouns: `adapter`, `held-out gold`, `structured edit`, `evaluator receipt`, `approval gate`. Expand an unfamiliar acronym on first use. Keep terms stable across the article and the linked repository.

Use paragraphs to advance the argument. A paragraph should answer one reader question, then earn the next. Lists work for explicit limits, steps, or comparisons. They are weak when they replace reasoning.

Describe cause and consequence. “The planner cannot change the evaluator because the evaluator path is protected” tells the reader more than “the system is robust.”

Avoid these habits:

- contrast templates such as `not X, but Y` when they only add rhythm;
- em dashes used as a substitute for a precise sentence break;
- superlatives, “production-ready,” “powerful,” “seamless,” “revolutionary,” and similar labels without measured support;
- stage-managed suspense, rhetorical questions, and stakes that the project has not demonstrated;
- a component inventory presented as an argument;
- claims that hide scope: “solves,” “guarantees,” “fully autonomous,” “secure,” or “works in production.”

Specificity is the standard. Use “the benchmark has six records per stage” when that is the relevant fact. Use “the local permission model is not an operating-system security boundary” when that is the relevant limit.

## Tone and structure

Borrow the durable qualities visible in strong project writing: an identifiable decision, a real operating context, evidence available to the reader, and clear ownership of the final decision. Do not imitate another author’s metaphors, cadence, sentence length, or signature phrases.

The article may use a first-person plural when it reports a decision made during the project. Use it sparingly. Prefer direct descriptions of the artifact when ownership is not relevant.

The repository README answers “what is this and how do I run it?” The article answers “why did this design deserve to exist, and what does its evidence say?” Keep the two jobs distinct.

## Editorial review

Run this review before a draft is published.

### Argument

- Can a reader state the governing engineering judgment after the first third of the post?
- Does every section advance that judgment?
- Does the conclusion give a useful next action without repeating the introduction?

### Claims

- Does every metric link to an artifact that contains the underlying value?
- Are benchmark scope, comparator, baseline, and limitations stated accurately?
- Has every current command been run or checked against the current release state?
- Does the text avoid claiming customer impact, scale, reliability, or security beyond the evidence?

### Voice

- Does each sentence contribute information, reasoning, or a necessary transition?
- Are contrast constructions carrying meaning rather than serving as cadence?
- Could a vague adjective be replaced with a mechanism, metric, or boundary?
- Would an experienced engineer recognize the failure mode and trade-off without being told how to feel about it?

### Artifact handoff

- Is the repository linked near the beginning and at the runnable call to action?
- Do readers have one short path to reproduce or inspect the main result?
- Do deeper repository documents hold the setup detail, full receipts, and architecture narrative?

## Research foundations

This guide applies the reader-centered structure and direct language recommended by [Google Technical Writing](https://developers.google.com/tech-writing/one/words), [Write the Docs](https://www.writethedocs.org/guide/writing/beginners-guide-to-docs/), and [GOV.UK’s writing guidance](https://guidance.publishing.service.gov.uk/writing-to-gov-uk-standards/writing-guidelines/). The article/repository split also follows the evidence-first pattern in the [Vendor vs Valor post](https://sitaniya.com/blog/vendor-vs-valor) and its [runnable repository](https://github.com/rsitaniya/vendor-vs-valor).
