# Security model

**Reader:** a reviewer deciding what the local benchmark harness enforces and where that enforcement ends.

`dev-flywheel` protects the integrity of a reviewed local workflow. It is not a multi-tenant service. Do not expose it to untrusted callers without separate authentication, authorization, rate limits, secret handling, telemetry controls, and operational hardening.

## Security claim

The documented implementer cannot read the answer key or write to the worktree. It returns structured edits. A guarded orchestrator validates those edits, runs tests and the evaluator, then waits for a human decision. The controls protect that workflow from accidental evaluator contamination and unreviewed mutation. They do not protect against an operator with broader local permissions.

The read and write boundaries are separate lists enforced by separate mechanisms, because they are separate questions. `[protected].paths` names what the implementer may not **write**, checked by `check_protected_paths.py` inside the single write entry point. `[protected].unreadable` names what it may not **read**, checked by an agent-scoped hook before each `Read` and `Grep`. Unifying them would either blind the implementer to engine code it must read against, or leave gold readable.

## Threats, controls, and residual risk

| Threat or failure mode | Control | Residual risk |
|---|---|---|
| Implementer writes directly to the repository | The implementer holds `Read`, `Grep`, and `Glob` only. It has no Bash, Edit, or Write tool grant. | The orchestrator and a human may hold broader permissions. |
| Submitted change modifies gold, fixtures, evaluator, engines, or receipts | `apply_edits.py` is the sole write entry point. It invokes the protected-path guard before any write and fails closed when no configuration resolves. | Protection is scoped to configured paths and the documented entry point. |
| Edit applies to the wrong source state | Each `old_string` must occur exactly once before a write. The full edit list is atomic. | A correct exact match can still express poor engineering. |
| Diff parser misses a rename, copy, or symlink trick | The implementer cannot express those operations. Its contract contains only file replacement edits. | This property depends on the implementer using the documented contract. |
| Implementer reads held-out answers | A `PreToolUse` hook declared in `.claude/agents/implementer.md` runs `scripts/check_readable.py` before every `Read` and `Grep` that subagent makes, denying anything under `[protected].unreadable`. It walks a grepped directory instead of matching its name, so held-out files cannot be reached through a parent, and it judges a call that names no path at all as the working directory the tool would search anyway — `Grep(pattern=...)` with no `path` is a cheaper reach for gold than any parent directory, and treating "no path" as "nothing to judge" was a fail-open hole this guard shipped with. It fails closed when no configuration resolves. | A hook is a tool-call interception, not a filesystem permission. It binds the implementer only. |
| A held-out path is read by the orchestrator or a human session | `.claude/settings.json` denies `Read`/`Grep` on gold and fixtures for every session in the repository. This is the condition the committed receipts were authored under. | `runs/` is deliberately readable: Gate 2 shows receipts and the trial skill writes a report it must read back. A determined operator can change either file. |
| The read guard cannot resolve which engagement is active | It denies every read rather than guessing, since guessing wrong applies another engagement's unreadable list. | The fail-closed state is total: the implementer cannot read ordinary app source either, so a cycle started in that state produces nothing. `/dev-loop` STEP 1 refuses to start rather than failing later. |
| The read boundary is silently removed | CI asserts that `implementer.md` still declares the hook, still matches `Read|Grep`, still holds only `Read, Grep, Glob`, that `runs/` has not returned to the session-wide deny list, and that every session-wide gold and fixture deny is still **present** — the negative assertion alone once let the row above be deleted with CI green. | CI proves the wiring exists, not that Claude Code honoured it in a given run. |
| A change passes HTTP tests while harming domain correctness | Gate 2 runs the configured evaluator and compares it with the pre-cycle baseline. Regression fires on a drop in `fully_correct_rate` or in any mapped field's `field_yield`; the latter needs no gold, and is the only one of the two that can fire on the real splits at all. | The evaluator only detects properties represented by its oracle. Yield establishes that a field produces values, never that they are the right values. |
| Local work is overwritten | The orchestrator aborts on a dirty worktree. | It cannot protect work created after the check or outside the repository. |

## The score-feedback channel

The synthetic development evaluator exposes aggregate results at every cycle. Repeated feedback can become a search signal. An agent could optimize the dev score without learning a rule that transfers.

The real MaDI-Bench configuration addresses that risk with a separate source distribution, schema gold, and adapter directory. Its raw columns do not overlap with the synthetic source. The trial harness logs evaluator invocations, making oracle use observable. The separate trial is evidence against one form of overfitting. It does not eliminate overfitting risk or establish generalization beyond its measured task.

## Data and network boundaries

- Raw real MaDI-Bench data is downloaded locally and ignored by Git. See the [data license notice](engagements/madi_onboarding/DATA_LICENSE_NOTICE.md).
- Usage telemetry is append-only. Query parameters are recorded verbatim. Treat the local usage log as non-secret.
- `X-Usage-Source` and run IDs are caller-controlled. A deployed service must assign provenance server-side.
- Telemetry is read into memory. Rotate, bound, and harden it before high-volume use.
- The simulator rejects a URL join that leaves its configured origin.
- `record_id_hash` uses a keyed HMAC. The fallback development key is not secret. Set `RECORD_ID_HASH_KEY` in any real deployment.

## Operational limits

- `/reconcile` is fixture-scale. A production entity-resolution system needs blocking, resource limits, monitoring, and recovery controls.
- Telemetry failure is fail-open. A logging failure does not turn a served request into a 500.
- Source-system path values are validated and adapter paths must resolve under the configured adapter directory.
- Batch and reconciliation inputs are bounded locally. Those bounds are not capacity planning.

## What this document does not claim

- OS-level isolation of the evaluator or data.
- Safe operation in a public or multi-tenant deployment.
- Immunity from a malicious or privileged local operator.
- A complete defense against poor adapters, weak oracles, or unsupported data volumes.

The [delivery-system architecture](docs/DELIVERY_SYSTEM.md) explains how these controls fit the loop. Report a security-relevant issue through the repository’s GitHub issues.
