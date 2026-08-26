# Project blog writing guide and dev-flywheel launch post

## Purpose

Create a reusable writing guide for canonical project-launch posts and apply it to dev-flywheel on sitaniya.com. The post should lead with senior/principal FDE judgment, then give a reader a credible route into the runnable repository.

## Audience and outcome

The primary reader is an engineering leader or technical reviewer assessing delivery judgment. A successful post leaves that reader with a clear view of the project's control boundary and enough evidence to inspect or run the repository.

## Reusable guide

Create `docs/PROJECT_BLOG_WRITING.md` in dev-flywheel. It will define:

- reader and desired action;
- a single governing engineering idea;
- a claim ledger that binds material claims to evidence or a stated limit;
- launch-post order: operational tension, principle, mechanism, evidence, limits, runnable next step;
- direct, concrete prose rules and a review checklist;
- editorial failure modes, including empty binary contrast, vague claims, component inventories, and duplicated README material.

The guide takes its approach from the Vendor vs Valor launch post and its repository evidence model, plus technical-writing guidance on reader needs, term consistency, short runnable paths, and clear links. It will not copy another post's cadence or metaphors.

## Canonical post

Create `sitaniya.com/app/blog/dev-flywheel/page.tsx` and list it on the home and blog-index cards. Use the working title **An agent should not certify its own patch**.

The post will be 1,200–1,500 words and cover:

1. why HTTP success does not establish integration correctness;
2. separation of proposal, implementation, evaluation, and approval;
3. the repository's adapter-loop mechanism;
4. the committed Forbes onboarding receipts;
5. explicit local-benchmark and fixture-scale limits;
6. a concise `uv`-based route to the repository.

No new visual asset is needed. The post will link to the repository and its receipts rather than duplicate technical documentation.

## Verification

- Recheck every metric, command, and limitation against the final dev-flywheel release state.
- Run the site lint/build checks.
- Verify blog-card, post, repository, and receipt links.
- Review the guide and post for binary cadence, invented stakes, vague adjectives, rhetorical filler, and unsupported claims.
