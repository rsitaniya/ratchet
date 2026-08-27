# Security model

**Reader:** a reviewer deciding what the local benchmark harness enforces and where that enforcement ends.

`dev-flywheel` protects the integrity of a reviewed local workflow. It is not a multi-tenant service. Do not expose it to untrusted callers without separate authentication, authorization, rate limits, secret handling, telemetry controls, and operational hardening.

## Security claim

The documented implementer cannot read the answer key or write to the worktree. It returns structured edits. A guarded orchestrator validates those edits, runs tests and the evaluator, then waits for a human decision. The controls protect that workflow from accidental evaluator contamination and unreviewed mutation. They do not protect against an operator with broader local permissions.

## Threats, controls, and residual risk

| Threat or failure mode | Control | Residual risk |
|---|---|---|
| Implementer writes directly to the repository | The implementer holds `Read`, `Grep`, and `Glob` only. It has no Bash, Edit, or Write tool grant. | The orchestrator and a human may hold broader permissions. |
| Submitted change modifies gold, fixtures, evaluator, engines, or receipts | `apply_edits.py` is the sole write entry point. It invokes the protected-path guard before any write and fails closed when no configuration resolves. | Protection is scoped to configured paths and the documented entry point. |
| Edit applies to the wrong source state | Each `old_string` must occur exactly once before a write. The full edit list is atomic. | A correct exact match can still express poor engineering. |
| Diff parser misses a rename, copy, or symlink trick | The implementer cannot express those operations. Its contract contains only file replacement edits. | This property depends on the implementer using the documented contract. |
| Implementer reads held-out answers | Claude Code deny rules block its `Read`, `Grep`, and `Glob` access to fixtures, gold, and receipts. | Deny rules are tool grants, not filesystem permissions. |
| A change passes HTTP tests while harming domain correctness | Gate 2 runs the configured evaluator and compares it with the pre-cycle baseline. | The evaluator only detects properties represented by its oracle. |
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
