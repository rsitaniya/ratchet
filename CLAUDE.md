# dev-flywheel — Agentic Dev Loop

The orchestration, traffic generation, structured-edit validation, and gates are domain-free;
everything domain-specific is named in one `flywheel.toml` and an
`engagements/<name>/` package — see `docs/ADAPTING.md`. Two configs in this repo
select two different datasets, protected sets, and oracles against the same loop:
`engagements/madi_onboarding/flywheel.toml` (synthetic dev fixtures, scored every
cycle) and `flywheel.real.toml` (real MaDI-Bench data, the held-out test split).

The reference engagement, `engagements/madi_onboarding/`, points the generic loop
at a partner-data onboarding API benchmarked on MaDI-Bench, with a **held-out
evaluator** the loop is forbidden to edit. It selects itself purely via
`FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml`.

## Quick start

```bash
# 0. Export the engagement config BEFORE launching Claude Code — the
#    implementer's read-guard hook inherits Claude Code's own environment,
#    and a Bash step's export never reaches it.
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml

# 1. Install dependencies
uv sync --all-extras --locked

# 2. Point the loop at the reference engagement and start its API
export FLYWHEEL_CONFIG=engagements/madi_onboarding/flywheel.toml
export USAGE_LOG_PATH=$(uv run python scripts/flywheel_config.py --get app.usage_log)
uv run uvicorn "$(uv run python scripts/flywheel_config.py --get app.module)" --reload

# 3. Build the replay traffic the config points at (in a second terminal),
#    then run the simulator
uv run python engagements/madi_onboarding/to_replay.py --source forbes
/simulate

# 4. Run one full agentic development cycle
/dev-loop

# Bonus: run cycles continuously with Claude Code's built-in loop runner
/loop /dev-loop
```

## Key files

| File | Purpose |
|------|---------|
| `flywheel.toml` | **The only seam between the loop and a specific API** — app module, evaluator, required analyzer, protected paths. One per app/split; this repo ships `engagements/madi_onboarding/flywheel.toml` (dev) and `flywheel.real.toml` (test) |
| `usage_log.jsonl` | Runtime product signal (gitignored; auto-created by API traffic) |
| `scripts/simulate.py` | Schema-driven simulator (called by /simulate skill) |
| `scripts/flywheel_config.py` | Loads the active `flywheel.toml` (via `FLYWHEEL_CONFIG`); `--get KEY` accessor for shell steps |
| `scripts/check_protected_paths.py` | Rejects any patch touching held-out evaluators/gold/fixtures/`runs/` (`[protected].paths`); fails closed if no config resolves |
| `scripts/check_readable.py` | The implementer's READ boundary (`[protected].unreadable`), run as a `PreToolUse` hook from `implementer.md`'s frontmatter so it binds that subagent only; fails closed |
| `scripts/cycle_log.py` | Per-cycle delivery telemetry — phase wall-clock, gate time, outcome, resubmissions, metric deltas; `report` derives cost per accepted change |
| `scripts/apply_edits.py` | The single guarded entry point for landing structured edits — runs the protected-path guard, then validates every edit's exact match, then writes, in that order, atomically |
| `engagements/madi_onboarding/` | Reference engagement: partner-data onboarding, ingest app, adapters, protected evaluator, its own analyzer, case study |
| `tests/` | FastAPI TestClient tests — run with `uv run pytest tests/ -v` |
| `docs/ADAPTING.md` | How to point the loop at your own API |
| `.claude/agents/` | The `implementer` subagent (read-only — orchestrator writes) |
| `.claude/skills/` | Orchestrator skills: simulate, dev-loop, dev-loop-trial |

## Conventions

- **One subagent, `implementer`, and its restriction is mechanical.** It holds `Read, Grep, Glob` — no Bash, no Edit, no Write — and returns structured edits as its only mutation request. A `PreToolUse` hook in its own frontmatter (`check_readable.py`) blocks it from reading fixtures, gold, or `runs/` at the tool level. That hook is agent-scoped on purpose: a session-wide deny also blocked the orchestrator from receipts it needs at Gate 2. Everything else in the loop (feature proposal, the guard, the evaluator) is deterministic code or a human at one of the two gates — not a second or third subagent role.
- **Tests use FastAPI TestClient** (in-process). The simulator uses httpx against the live server.
- **Server must be running** before invoking /simulate or /dev-loop.
- **usage_log.jsonl is runtime telemetry.** It is append-only during a run, but gitignored so local simulator traffic does not dirty the submission.
- **Loop closure:** The simulator re-fetches /openapi.json each cycle, so new endpoints are exercised automatically without editing the simulator.
- **Continuous mode:** Use `/loop /dev-loop`; `/dev-loop` itself is one complete cycle. `/dev-loop-trial` is a separate measurement mode that auto-answers both gates to measure agent convergence — never a mode for landing real changes.
- **No domain knowledge in the loop.** `scripts/` and `.claude/` must stay generic. Anything app-specific belongs in `flywheel.toml` or an `engagements/<name>/` package's own analyzer (`[app].analyzer` is required — there is no generic fallback).
- **Every submission goes through `scripts/apply_edits.py`, never a hand-written diff.** The implementer returns structured `{file, old_string, new_string}` edits, plus `VERIFICATION` (one row per mapped field, tracing a real source value through the chosen normalizer) and `LIMITS` (what the change does not do). A `VERIFICATION` row whose result is an error is a hard rejection at STEP 4, before tests ever run — that block exists so a mapping that declares a correspondence and normalizes nothing cannot be submitted without the agent writing down that it is dead. It does not calculate hunk headers or line counts. `apply_edits.py` runs the protected-path guard, validates every edit's `old_string` against current content, then writes atomically in that order. `.claude/settings.json` also denies `Bash(git apply:*)`, so a hand-crafted diff is not a shorter path. This is not an OS-level boundary: the orchestrator holds Edit/Write directly and could evade it deliberately. See `SECURITY.md`.
- **Two human gates + a protected evaluator.** The loop blocks at Gate 1 (approve the proposal) and Gate 2 (approve the exact tested patch after the app's `[app].evaluator` runs). The implementer may never edit paths in `[protected].paths` (held-out evaluator, gold, fixtures, `runs/`) — `check_protected_paths.py` enforces this and fails closed if no config resolves. It may never *read* paths in `[protected].unreadable` — `check_readable.py` enforces that, walks a grepped directory rather than matching its name so gold cannot be reached through a parent, and treats a call naming no path as the working directory — the tool's own default target, and the cheapest reach of all.
- **The loop measures itself.** Every cycle writes one delivery record via `cycle_log.py`: phase wall-clock, `agent_seconds` (every phase with no operator in it), outcome, resubmissions, submission size, evaluator calls, metric deltas. Human decision time is *not* recorded: a gate span runs from the previous mark to the human's answer, so it also contains the orchestrator composing proposals or rendering the diff, and nothing marks the boundary — a "human minutes" number from that span would be agent time wearing a human label. CI recomputes the published economics from the committed records and fails on drift. **Every config appends to one log**, because cost per accepted change is a property of the loop, not of a source, and a per-config log would split that sample across the very number the repo publishes. Metric keys carry the source instead (`fullcontact.schema_f1`), so a per-source claim is derived by grouping; a CI check that hardcodes one source breaks the moment a second is onboarded. A control firing (`regression-blocked`, `guard-rejected`, `validation-failed`, `tests-failed`) is a distinct outcome from a human declining (`reverted`). The model marks phase boundaries; it never computes a duration or copies a score. Token cost is deliberately not recorded — no reliable per-subagent count exists, and an invented one would undermine every other number.
- **No CHANGELOG.md.** `git log` plus the receipts under `runs/` are the change record. Behaviour changes go in the docs that describe the behaviour.
- **Adapters are data.** An engagement grows mostly by adding declarative config the app reads (e.g. onboarding adapters), not agent-written code; new code is reserved for genuinely new behavior and is covered by tests + the evaluator.

## Writing style — no AI slop

Code and docs read like an engineer wrote them, not like an LLM wrote marketing copy. Keep clean-code / Karpathy discipline on: clear, concise, efficient, minimal.

- **Code:** minimal comments — only load-bearing "why" (a constraint the code can't show). No speculative abstractions, no dead code, match the existing pattern.
- **Docs:** no emoji in diagrams or headers, no rhetorical/marketing section titles, no bold-spray, no essayist asides. Keep the substance and the honest numbers; cut the flourish.

## Engineering discipline (hard-won)

A green test suite proves the happy path, nothing more. Enforce these or the loop's safety claims are theatre.

- **Security boundaries are validated adversarially.** Never parse a tool's text output to make a security decision. Use a structured field the tool produced directly, such as an edit's own `file` path. The structured-edit contract cannot express rename, copy, or symlink operations, so those operations never reach the guard as disguised text.
- **Boundaries are mechanism, not etiquette.** "Read-only" means the tool grant is Read/Grep/Glob (no Bash). "Held-out" gold means the agent cannot read it, not just cannot write it. Fail closed: if the guard cannot determine what a patch touches, reject it.
- **Wire and run end-to-end before claiming it works.** Grep for every component the docs reference and confirm something selects it. Don't build an artifact and its harness in parallel and assume they connect.
- **Prose never outruns code.** Re-verify factual claims (test counts, capability lists, gate counts) against reality on every doc change.
- **Docs update in the same pass as the code, not after.** README, CASE_STUDY.md, SECURITY.md, ADAPTING.md, and this file describe behavior, gates, and numbers that live in code. A change to what they describe (a new gate, a wired check, a real vs. claimed metric) updates the doc in the same change — never a follow-up, never left stale.
- **State the threat model.** This repo is a local, single-operator benchmark harness, not a hardened multi-tenant service. Say so where the claims live, so scope is explicit.
- **A boundary binds the party it names.** A control scoped wider than the thing it describes is a bug, not extra caution — the session-wide read deny also blocked the orchestrator from receipts Gate 2 has to show. Scope it to the agent, then test the bypass, not the front door — and note that the guard is not the whole party either: the tool's *default* argument is a bypass too. `Grep(path=parent)` was tested and denied while `Grep` with no `path` at all, which searches the same tree, was allowed for a release, because "no path" read as "nothing to judge". Two tests asserted that as correct behaviour.
- **Prune every pass; dead code is not defended by its tests.** Hunt what should not exist: a one-caller abstraction, a config key nothing reads, a fallback the real implementation superseded. Never argue "it has tests, so it is load-bearing" — ask what calls it first. A test over unused code makes deletion look risky and proves nothing; delete both. The calculator example and the generic analyzer fallback left this way.
- **When the model keeps failing a step, change the contract.** Two of five trials returned a malformed diff because a read-only agent was hand-computing hunk headers it had no shell to verify. The fix was the structured-edit format, not a retry loop. Measure the failure, find the unverifiable part, remove it from the model's job.
- **Unmeasured is not zero, and an adjective is a missing number.** `value_recall` is `null` on the real split, never `0.0`. "Controlled delivery" is a throughput claim, so cycles are measured. Where a number genuinely cannot be had — per-subagent token cost — name it and say why rather than leaving the gap looking accidental.
- **Surface the understated signal.** The strongest evidence here is routinely buried: zero-domain-config discovery lives in a CI step, not the README's reuse claim. When the proof in the repo is stronger than the claim, move the proof to the claim.

## Precedence

The user's global CLAUDE.md rules apply here by default. If one of them conflicts
with this repo's own plan, this file, or its established execution conventions,
do not resolve it silently — surface the conflict and let the user decide.
