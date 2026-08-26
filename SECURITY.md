# Security model

## Threat model

dev-flywheel is a **local, single-operator development loop and benchmark harness**,
not a hardened multi-tenant service. It assumes:

- One operator runs the loop, the API, and the simulator on their own machine.
- The operator is trusted; the API is not exposed to untrusted callers.
- The adversary that matters is **the loop's own agent** trying to make its metrics
  pass without doing the work — the thing the oracle-safety design defends against.

Two consequences follow. First, the loop's safety guarantees (below) are the real
product and are enforced by mechanism. Second, deployment-grade hardening (auth,
rate limiting, provenance you can't spoof) is out of scope by design — but the
robustness fixes below are in place so the services behave sanely under bad input.

## Guarantees the loop enforces (in scope)

- **The agent cannot edit what scores it.** Every applied patch — code, docs,
  anything — passes `scripts/check_protected_paths.py` before `git apply`. Touched
  paths come from `git apply --numstat -z` (Git does its own unquoting), unioned with
  a hardened text parse for rename/copy sources; an unparseable patch is rejected
  (fail closed). Protected paths cover the evaluator, matching/fusion engines, gold,
  fixtures, the config that declares them, and the loop's own machinery.
- **Planners are read-only by tool grant.** `feature-suggester` and `implementer` run
  with Read/Grep/Glob only (no Bash), so their sole mutation path is the unified diff
  the orchestrator validates and applies.
- **Gold and fixtures are unreadable, not just unwritable.** `.claude/settings.json`
  denies `Read`/`Grep` on `**/fixtures/**` and `**/gold_*.json` project-wide. Tool
  grants already made planners write-blind; this makes them read-blind on the answer
  key too, so "held-out" is enforced by the permission system, not by an instruction
  the agent could ignore. A planner has no Bash, so it has no other path to file
  contents.
- **Two human gates.** Gate 1 approves the proposal; Gate 2 approves the exact tested
  patch after all edits and the held-out evaluator have run.
- **A dirty working tree aborts the cycle**, so a Gate-2 revert only ever discards the
  cycle's own changes, never unrelated work.

## Robustness hardening (in place)

- **Telemetry is fail-open.** A usage-log write failure is swallowed to stderr and
  never turns a served request into a 500; an unhandled handler crash is still
  recorded (as a 500 with the exception name) because logging runs in `finally`.
- **No path traversal.** `source_system` is constrained to a safe token at the API
  boundary (422) and in `load_adapter`, which also verifies the resolved path stays
  under `adapters/`.
- **Bounded inputs.** `/calculate/batch` and `/reconcile` cap array length (matching
  is O(n·m)), so an unbounded array cannot exhaust resources.
- **The simulator cannot leave its origin.** `safe_url` refuses any URL join that
  changes `base_url`'s scheme or host.

## Residual limitations (out of scope; know these before exposing anything)

- **The deny rule is a Claude Code permission, not a filesystem permission.** It
  blocks the `Read`/`Grep` tool calls a planner subagent makes; it does not chmod the
  files. A human editing the repo outside Claude Code, or a future tool grant that
  adds Bash to a planner, is outside this control. Overfitting a *writable* normalizer
  or adapter to the visible source records (without ever seeing gold) is still
  possible in principle — Gate-2 human review and the fact that the evaluator returns
  only aggregate scores (never per-field diagnostics) are what keep that from being a
  practical attack, not a filesystem boundary.
- **Telemetry provenance is caller-set.** `X-Usage-Source` / `X-Run-Id` are trusted so
  the local simulator can tag its own traffic. In an exposed deployment, assign
  provenance server-side and authenticate simulator traffic instead.
- **Recorded `inputs` are verbatim.** Query params are logged as-is; do not send
  secrets or PII to a service whose usage log you treat as signal.
- **The analyzer loads the whole log.** Fine at benchmark scale; add rotation/size
  bounds before pointing it at a high-volume production log.
- **Automatic 422 validation errors** use FastAPI's default schema, not the app's
  `ErrorResponse` shape.

## Reporting

This is a personal open-source project; open a GitHub issue for anything security-
relevant.
