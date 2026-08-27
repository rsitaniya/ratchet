# Security model

**Reader:** a reviewer deciding what the local benchmark harness enforces and what it does not.

## Scope

This is a local, single-operator development loop and benchmark harness. It is not a multi-tenant service and should not be exposed to untrusted callers without separate authentication, authorization, rate limiting, telemetry, and operational controls.

## Enforced workflow controls

| Claim | Mechanism |
|---|---|
| The implementer cannot write directly. | It holds `Read, Grep, Glob` only — no Bash, no Edit, no Write — and returns structured `{file, old_string, new_string}` edits, never a diff. This is its only mutation path. |
| Protected artifacts cannot be changed by a submitted edit. | `scripts/check_protected_paths.py` checks each edit's `file` path directly (no diff parsing — there is no diff) and fails closed if no `flywheel.toml` resolves. A rename, copy, or symlink write has no equivalent in the edit contract, so there is nothing to detect for any of them — the implementer cannot express those operations at all, not just none it has tried and been caught at. |
| The guard cannot be skipped by omission. | `scripts/apply_edits.py` is the single entry point that runs the protected-path guard, then validates every edit's `old_string` against current file content, then writes — in that fixed order, atomically (one bad edit blocks the whole submission). `.claude/settings.json` also denies `Bash(git apply:*)` directly, so hand-crafting a diff isn't a shorter path either. |
| Gold is not an implementer input. | Claude Code deny rules block the implementer's `Read`/`Grep` access to fixtures, gold files, and `runs/` (committed receipts — the converged answers to prior cycles). |
| A tested patch needs an accountable decision. | Gate 1 approves scope; Gate 2 approves the exact tested patch after tests and evaluator output. |
| A cycle cannot overwrite unrelated local work. | The orchestrator aborts on a dirty working tree. |

## Real-data test split and the score-delta channel

Every dev cycle scores against synthetic fixtures the implementer can never read, but the loop *can* observe the evaluator's aggregate score-delta each cycle. Over enough cycles that is a probing channel: an agent could in principle hill-climb against repeated score feedback instead of solving the mapping problem, and each cycle's evaluator output could anchor the next cycle's proposal toward whatever the last score rewarded.

The real MaDI-Bench data (`flywheel.real.toml`, `data/madi/`, never committed) is the answer to that channel, not just more test coverage: it is scored **once**, offline, never during a loop cycle, and the fitted synthetic adapter cannot transfer to it (the real and synthetic forbes source columns share no names). A loop that had learned to fit the synthetic fixtures' score-delta signal gains nothing from that on a distribution it never received feedback against. `evaluate.py`'s `FLYWHEEL_EVAL_LOG` (set by `/dev-loop-trial`) makes evaluator-invocation frequency an observable, not an assumption — a trial that consulted the oracle an unusual number of times per cycle is visible in the log, not just in the final score.

## Residual limits

- Claude Code deny rules are not filesystem permissions; changing tool grants changes the boundary. For the implementer subagent (no Bash) this closes the loophole entirely — a returned diff is its only route to the tree. For a Bash-holding session (the orchestrator, or a human), the deny rules are a strong deterrent, empirically also matching `Bash` commands that name a denied path as an argument (e.g. `cat` on a `runs/` file is refused) — but this is a heuristic over the command text, not a kernel-level permission, and a sufficiently indirect invocation could still evade it.
- A writable adapter or normalizer can still be poor engineering. Aggregate evaluator output and human review limit, but do not eliminate, overfitting risk against the synthetic dev fixtures — this is exactly what the real-data test split above exists to bound.
- `X-Usage-Source` and run IDs are caller-set. Assign provenance server-side in an exposed deployment.
- Query parameters are recorded verbatim. Do not treat the local usage log as a secret-safe store.
- Telemetry is append-only and read into memory. Rotate, bound, and harden it before high-volume use.
- `/reconcile` is fixture-scale; production entity resolution needs blocking and resource limits.
- `record_id_hash` in telemetry is a keyed HMAC (`RECORD_ID_HASH_KEY`), not a bare hash, so it resists dictionary/rainbow-table recovery from a guessable id space — but the app falls back to a fixed, non-secret dev key when the env var is unset. Set `RECORD_ID_HASH_KEY` in any real deployment.

## Robustness measures

- Telemetry is fail-open: a logging failure does not turn a served request into a 500.
- Source-system path values are validated and adapter paths must resolve under `adapters/`.
- Batch and reconcile inputs are bounded.
- The simulator rejects a URL join that leaves its configured origin.

Report a security-relevant issue through the repository’s GitHub issues. See [Delivery system architecture](docs/DELIVERY_SYSTEM.md) for the controls in context.
