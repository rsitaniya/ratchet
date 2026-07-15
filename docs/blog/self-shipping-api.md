# I built a calculator API that ships its own features

*A small experiment in closing the loop between telemetry and the agent that writes your code.*

---

Most "AI writes code" demos stop at the diff. You describe a feature, a model emits
some code, you paste it in. The impressive part is the generation — which is also the
part that's now commoditised.

The part nobody demos is the rest of the loop: **deciding what to build**, proving it
works, and making the next iteration aware of what the last one shipped. That's where
the actual engineering is. So I built the smallest possible thing that closes it.

The result is a calculator API. The calculator is deliberately, aggressively boring —
seven arithmetic operations. **The calculator is not the project.** The loop around it
is.

## The loop

Every request the API serves is appended to `usage_log.jsonl` by a ~20-line middleware.
An analyzer turns that raw log into a signal report. An agent reads the report and
proposes features — **citing the numbers**. I approve one. A second agent returns a
unified diff. An orchestrator validates it with `git apply --check`, applies it, and
runs the tests. Then the simulator re-reads `/openapi.json`, notices an endpoint that
didn't exist sixty seconds ago, and starts generating traffic against it.

Which becomes the signal for the next cycle.

```
simulate → usage_log.jsonl → analyze → suggest → [HUMAN] → implement
    ↑                                                          ↓
    └────────── new endpoint in /openapi.json ←── test ←── git apply
```

Here's what actually shipped, and why:

| Version | Feature | The signal that caused it |
|---------|---------|---------------------------|
| `0.2.0` | `mod` | 2/129 calls returned **HTTP 422 on `op=modulo`** |
| `0.3.0` | `abs` | **82 calls with a negative `a`** |
| `0.5.0` | `safe_divide` | Repeated **`b=0`** traffic taking a hard `400` |

I didn't plan any of those. I approved them.

## Three things I'd take to a real system

### 1. A 404 is a feature request

The middleware records requests to paths that **don't exist**. Most telemetry pipelines
filter these out as noise — malformed traffic, someone's typo, a scanner.

But a `GET /sqrt` that 404s nine times isn't noise. It's the single highest-quality
product signal in the entire system: *somebody tried to use a thing you haven't built.*
Successful requests tell you what people do with what exists. 404s tell you what they
wanted instead. The second question is the more interesting one, and it's usually
sitting in your logs being discarded.

Once you frame unmet demand as the primary input, the analyzer's most valuable section
writes itself:

```
── Requested-but-missing endpoints (HTTP 404) ──────────
  /sqrt: 9 requests to a path that doesn't exist — candidate new endpoint
```

### 2. Planners are read-only. One component writes.

The moment you have several agents touching a repo, you have a write-safety problem: a
half-applied edit, two agents racing the same file, a "fix" that silently reverts
another. The usual answer is a framework with a transaction model.

I didn't need one, because `git` already is one.

Every subagent here — `feature-suggester`, `implementer`, `docs-updater` — is declared
with **read-only tools**. They cannot write. Their entire output contract is a **unified
diff**. The orchestrating skill is the only component with write access, and it runs
`git apply --check` before touching the working tree.

This buys three things almost for free:

- **No partial writes.** A malformed patch fails at `--check`, loudly, having changed nothing.
- **Auditable handoffs.** The contract between agents is a diff — the most reviewable artifact in software.
- **A real gate.** `git apply --check` is a deterministic validator. It doesn't need to be prompted, and it can't be talked out of its answer.

The general principle: **don't make the model do the deterministic work.** Patch
validation, version bumping, and test gating are code. The model's job is the language
part — reading a signal report and arguing for a feature.

### 3. The human gate has to live in the parent

I wanted approval inside the suggester subagent — it has the context, so it should ask.

It can't. Subagents run headlessly; they have no channel to block for input. So the
approval step has to sit in the orchestrating skill, which means the orchestrator must
own the whole cycle rather than delegating it.

That's not a workaround. That's the execution model telling you where the boundary
goes, and the design is better for having listened: there's exactly one blocking step,
in exactly one place, and it's the one decision that should be mine.

## The part that makes it a flywheel

The easy version of this project hardcodes the simulator: a list of endpoints, some
handwritten payloads. It works, and it's dead on arrival — because every feature the
loop ships requires you to go teach the simulator about it. The loop needs a human to
turn the crank.

So the simulator knows nothing. It fetches `/openapi.json` and synthesizes requests
from the JSON Schema — resolving `$ref`, picking from `enum`, walking `anyOf`/`oneOf`,
recursing into arrays and nested objects. Give it a new `GET`, a `POST` with a body, a
path parameter — it exercises them, having never been told they exist.

That's the whole trick. **Nobody edits the simulator when a feature ships.** The output
of one cycle is automatically the input of the next, and CI asserts it: on every push a
job boots the API, runs the simulator against it, and does it again with all domain
config deleted to prove the generic path still works.

## Does it work?

It's a calculator, so let's be honest about scope: the search space is tiny, and a loop
proposing arithmetic operations from a log of arithmetic operations is not AGI. The
signals are real but they're shooting fish in a barrel.

What I think does generalise is the shape:

- Telemetry that records failure and absence, not just success.
- Agents constrained to propose, with a deterministic component doing every mutation.
- One human gate, placed where the execution model actually allows it.
- Machinery that adapts through a schema rather than a hardcoded list, so the loop closes without a human turning the crank.

None of that is model-specific, and none of it gets obsolete when the next model lands.
It's the boring scaffolding around the diff — which, increasingly, is the only part
that's still yours to get right.

---

*Code: [github.com/rsitaniya/dev-flywheel](https://github.com/rsitaniya/dev-flywheel) — Apache-2.0.
Point `flywheel.toml` at your own FastAPI app and the loop runs against it; the calculator is just what shipped with the box.*
