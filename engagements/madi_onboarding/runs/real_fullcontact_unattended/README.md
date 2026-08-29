# Real fullcontact — first run (superseded, timings unusable)

**Purpose:** preserve the first complete fullcontact run so a reviewer can check
its mapping result, which stands. Its *delivery timings* do not, which is why it
was re-run rather than published.

`flywheel.real_fullcontact.toml` selects MaDI-Bench's 1,931-record fullcontact
CSV, whose columns are anonymized to `Attribute_1..6`. No header carries meaning,
so the mapping has to be inferred from record values — this is the harder of the
two real splits.

## What it reached

| Cycle | Commit | schema_f1 | Fields mapped that cycle |
|---|---|---:|---|
| baseline | `15af084` | 0.0000 | — (empty adapter) |
| 1 | `ebc0d56` | 0.5000 | `id`, `name` |
| 2 | `5b9daf8` | 0.9091 | `country`, `city`, `founded` |
| 3 | `9b7974c` | 1.0000 | `keypeople` |

Per-field yield at the end — the share of the 1,931 records that actually
produced a value, which needs no gold and is the number to read first:

| Target | Source column | Produced | Rate |
|---|---|---:|---:|
| `id` | `Attribute_1` | 1931 / 1931 | 1.0000 |
| `name` | `Attribute_2` | 1931 / 1931 | 1.0000 |
| `country` | `Attribute_3` | 1421 / 1931 | 0.7359 |
| `city` | `Attribute_4` | 1375 / 1931 | 0.7121 |
| `keypeople` | `Attribute_5` | 192 / 1931 | 0.0994 |
| `founded` | `Attribute_6` | 1056 / 1931 | 0.5469 |

`integrated_rate` is `0.00` at every cycle and cannot move: the source has no
column for `industry`, `assets`, or `revenue`, so a record can never carry every
required target attribute. That is a structural ceiling, not a result.
`value_recall` and `fully_correct_rate` are `null` — unmeasured, because the real
benchmark pins no normalized-value gold. Null is not zero.

## Why it was superseded

The delivery record is archived beside this directory as
`../delivery/cycles.2026-08-28-fullcontact-unattended.jsonl`.

| Cycle | Total | Agent | Gate 2 span |
|---|---:|---:|---:|
| 1 | 685.39s | 382.12s | 162.67s |
| 2 | 904.92s | 531.85s | 195.33s |
| 3 | 26499.96s | 393.51s | **25995.98s** |

Cycle 3's Gate 2 ran for 7.2 hours because the operator left the session with the
gate open. A gate span is measured from the previous mark to the human's answer,
so that span is almost entirely idle waiting. It dragged the published
wall-clock-per-accepted-change figure from roughly 13 minutes to 156, which
describes the operator's afternoon rather than the loop. Agent time was unaffected
(393.5s, in line with cycles 1 and 2).

The numbers here are therefore kept as evidence of *what the loop mapped*, and
not used for any throughput claim.

## Reproduce

Every file in this directory was reconstructed from the commits above, not
transcribed. For any cycle:

```bash
git worktree add --detach /tmp/wt <commit>
cd /tmp/wt
FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.real_fullcontact.toml \
uv run python engagements/madi_onboarding/evaluate.py \
  --fixtures <repo>/engagements/madi_onboarding/data/madi \
  --adapters /tmp/wt/engagements/madi_onboarding/adapters_real --sources fullcontact
```

`--fixtures` points back at the main checkout because `data/madi/` is gitignored
(fetched by `download_data.py`, which verifies pinned git blob SHAs). That is also
why CI cannot recompute these particular receipts the way it recomputes
`runs/forbes/` and `runs/reconcile/`: the real data is not in the repo, and its
download step is deliberately non-fatal so an external outage never reds the build.

The normalizers and tests each cycle added are in the commits, not duplicated here:
`git show <commit> -- engagements/madi_onboarding/normalizers.py tests/`.
