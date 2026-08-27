# Real-data convergence trials

**Question:** starting from an empty adapter, how did the measured implementer perform on the real MaDI-Bench Forbes mapping task?

These are measurement runs. Both gates were auto-answered, every run started from the committed empty `adapters_real/forbes.toml`, and the tree was reverted afterwards. They are not human-approved delivery cycles.

## Protocol

- **Runs:** 5
- **Cycle cap:** 5 per run
- **Configuration:** `flywheel.real.toml`
- **Traffic:** 300 replayed records from the 2,000-record real Forbes source
- **Evaluation:** schema-mapping F1 against the real source’s separate gold; the evaluator scores all 2,000 records
- **Convergence condition:** `schema_f1 == 1.0`

`value_recall` and `fully_correct_rate` are `null` because the real benchmark provides no value gold. `integrated_rate` remains `0.0`: the source has no `founded` or `city` data, so a complete canonical record is impossible regardless of adapter quality.

## Result

**All 5 trials converged in cycle 1.** Each ended at schema-mapping F1 `1.0`, with no regression and two evaluator invocations.

| Trial | Cycles | Schema F1 | Regression | Evaluator calls | First response issue |
|---|---:|---:|---|---:|---|
| 1 | 1 | 1.0 | none | 2 | malformed unified-diff hunk count |
| 2 | 1 | 1.0 | none | 2 | none |
| 3 | 1 | 1.0 | none | 2 | none |
| 4 | 1 | 1.0 | none | 2 | malformed unified-diff context |
| 5 | 1 | 1.0 | none | 2 | none |

All trials independently selected the same mapping:

```text
forbes_url       -> id        (identity)
company          -> name      (identity)
region           -> country   (country_to_iso)
business_segment -> industry  (identity)
asset_value      -> assets    (currency_to_usd)
sales_figure     -> revenue   (currency_to_usd)
```

`url` duplicates `forbes_url`. The source does not provide `founded` or `city`. Every trial left those fields unmapped rather than inventing a mapping.

## What the trial changed

The mapping result was reliable in this run. The diff mechanics were not. Two of five first responses contained a malformed unified diff. The old workflow asked a read-only implementer to calculate diff hunk headers it could not verify with Bash.

The current loop no longer accepts model-authored diffs. The implementer returns structured `{file, old_string, new_string}` edits. `scripts/apply_edits.py` validates every target and exact prior string, then applies the full submission atomically. The trial remains evidence of the old failure. The structured-edit contract is the design response.

## Limits

- The source mapping has low ambiguity. Seven raw columns map to distinct target concepts with few plausible alternatives.
- Five successes do not establish general agent reasoning ability or broad reliability.
- This is an auto-gated measurement. It does not demonstrate human approval quality.
- The raw real records are writable-protected but intentionally readable by the implementer, which needs their values to select normalizers. That is a looser tool boundary than the synthetic fixture split.
- Two evaluator calls per trial are reassuring at this scale. They do not prove that score-feedback probing cannot occur in a harder or longer run.

## Reproduce

```bash
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real.toml
uv run python engagements/madi_onboarding/download_data.py
uv run python engagements/madi_onboarding/csv_to_ingest.py --source forbes
uv run python engagements/madi_onboarding/prepare_real_eval.py
```

Then run `.claude/skills/dev-loop-trial/` with a chosen run count and cycle cap. Read the [real-data baseline](../real_forbes/README.md) first.
