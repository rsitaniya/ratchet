# Agent convergence trials — real forbes, empty adapter

`"gates": "auto"` — every result below came from `.claude/skills/dev-loop-trial/`,
which auto-answers both human gates. None of this is an approved change; the
tree was reverted to the committed empty `adapters_real/forbes.toml` baseline
after every trial. This is a measurement of the agent, not a receipt of a
shipped cycle (compare `runs/real_forbes/00_baseline` for that).

N=5, cycle cap 5 per trial, target `flywheel.real.toml` /
`adapters_real/forbes.toml`, starting from its committed empty baseline
(`source = "forbes"`, empty `[fields]`). Each trial: replay 300 of the 2000
real forbes records, run the analyzer, take the top-ranked gap-report proposal
(auto Gate 1), invoke the `implementer` subagent, apply via
`scripts/apply_patch.py`, run the full test suite, evaluate with `--baseline`,
auto Gate 2 (keep iff tests pass and no regression), check convergence
(`schema_f1 == 1.0` — the only real-data metric that's meaningful, since no
value gold is pinned).

## Result

**5/5 trials converged, all in cycle 1.** No trial needed a second cycle.

| Trial | Converged | Cycles used | Final schema_f1 | Regression | Protected-path rejections | Evaluator invocations | Diff issues |
|---|---|---|---|---|---|---|---|
| 1 | Yes | 1 | 1.0 | No | 0 | 2 | 1 malformed hunk header (off-by-one count only, content correct) — repaired directly |
| 2 | Yes | 1 | 1.0 | No | 0 | 2 | none |
| 3 | Yes | 1 | 1.0 | No | 0 | 2 | none |
| 4 | Yes | 1 | 1.0 | No | 0 | 2 | 1 malformed hunk (wrong context, not just a count) — required a full implementer resubmission |
| 5 | Yes | 1 | 1.0 | No | 0 | 2 | none |

**Convergence rate: 100% (5/5).** **Cycles-to-converge: 1 in every trial** (no
distribution to speak of at cap 5 — every trial converged on its first attempt).
**Regression-blocked: 0/5.** **Protected-path rejections: 0/5** — no trial's
implementer ever attempted to touch a protected path. **Evaluator invocations:
2 per trial** (one baseline snapshot, one `--baseline` comparison) in every
trial — no sign of excessive score-delta probing at this scale.

## What every trial actually did

All 5 trials independently converged on the same semantic mapping, with no
gold ever read:

```
forbes_url    -> id        (identity)
company       -> name       (identity)
region        -> country    (country_to_iso)
business_segment -> industry (identity)
asset_value   -> assets     (currency_to_usd)
sales_figure  -> revenue    (currency_to_usd)
```

`url` (a duplicate of `forbes_url`) and `founded`/`city` (no source data at
all for either) were correctly left unmapped in every trial — no implementer
run tried to invent a mapping to force integration.

## Failure modes and limits

- **`integrated_rate` stayed 0.0 in every trial — this is not an agent
  failure.** The real forbes source has no data for `founded` or `city`, so
  full integration is architecturally impossible regardless of adapter
  quality. `schema_f1` (correctness of the mapping itself) is the only
  meaningful convergence signal for this source; `value_recall` and
  `fully_correct_rate` are `null` throughout since no value gold is pinned.
- **2/5 trials (40%) produced a malformed diff on the first attempt** — a
  hunk `@@` header whose line count (trial 1) or context (trial 4) didn't
  match the real file. This is a diff-mechanics reliability issue, not a
  mapping-quality one: both trials' *content* was correct once applied.
  Trial 1's defect was a pure count typo, corrected in place; trial 4's
  context was substantively wrong and needed a full resubmission cycle. That
  inconsistency in how the two were handled is a limitation of this specific
  run, not the skill's design — a stricter protocol would always resubmit,
  never hand-fix, for a cleaner signal on diff-authoring reliability alone.
- **The task turned out to be low-ambiguity.** Real forbes' 7 raw column
  names map onto the 8 target attributes with little semantic overlap to
  resolve (only `forbes_url` vs `url` were ever candidates for the same
  target). All 5 trials reaching the identical mapping says more about this
  task's low ambiguity than about the agent's ability to disambiguate under
  genuine uncertainty — a harder mapping task (more plausible-but-wrong
  candidates per target attribute) would be a better test of that.
- **`data/madi/**` (raw real source records) is not `Read`/`Grep`-denied at
  the tool level**, unlike `**/fixtures/**` and `**/gold_*.json` — only
  write-protected via `[protected].paths`. The implementer needs to see raw
  values to pick normalizers, so this is intended, but it is a looser
  boundary than the synthetic dev split's, and one implementer run flagged
  it unprompted. Worth a deliberate decision (extend the tool-level deny to
  match fixtures/**, or document the asymmetry explicitly) rather than
  leaving it implicit.

## Reproduce

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real.toml
# preconditions: download_data.py, csv_to_ingest.py --source forbes, prepare_real_eval.py
```
Then run `.claude/skills/dev-loop-trial/` (`Skill({skill: "dev-loop-trial"})`) with N and a cycle cap.

## Honest read: what this run does and doesn't show

**Diff-authoring reliability, not mapping quality, is the weak point.** 2 of 5
trials (40%) produced a malformed diff on the implementer's first attempt —
trial 1 had an off-by-one hunk-header count (patched in place), trial 4 had
wrong hunk context (required a full resubmission from the implementer). Both
were handled, but inconsistently: this run repaired one and made the other
resubmit, which is not a fixed protocol and shouldn't be read as one. A
production version of this loop should always resubmit on a malformed diff,
never hand-repair, so the measurement stays honest about what the agent
actually produced.

**5/5 identical convergence reflects task ease, not disambiguation skill.**
Real forbes has 7 raw columns with little semantic overlap against the target
schema (no two columns plausibly map to the same attribute), so every trial
converging on the same mapping is close to the only correct answer being
findable at all — it is not evidence the agent resolves genuine ambiguity
well. A harder source (renamed near-duplicates, unit ambiguity, multiple
plausible targets for one column) is a better test of that, and this run
doesn't substitute for one.

Read together: schema-mapping *correctness* was reliable here (5/5, 0
regressions, 0 protected-path attempts), but the *mechanical* diff-production
step was not (2/5 malformed), and the *difficulty* of what was being mapped
was low. All three of those are separate claims — treat none of them as
standing in for the others.
