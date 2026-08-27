# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Removed
- **The bundled calculator example app** (`app/`, its tests, root `flywheel.toml`/`edge_cases.json`, and the standalone blog post about it). The MaDI onboarding engagement is now the repository's sole worked example. The zero-domain-config genericity proof that the calculator's CI job demonstrated — the simulator discovers and exercises every endpoint from `/openapi.json` alone, with no `[protected]` paths, edge cases, or signal config declared — moved to the `madi-engagement` CI job: it runs `scripts/simulate.py` in schema-random mode against the already-running MaDI app with `FLYWHEEL_CONFIG` unset, proving the same claim against a real, non-trivial app instead of a purpose-built fixture.

### Added
- **MaDI onboarding Stage 2: entity matching + data fusion.** A `POST /reconcile` endpoint matches records across two sources (declarative `matching_rules.toml` + named similarity functions incl. Jaro-Winkler, with blocking) and fuses matched records (declarative `fusion_rules.toml` with per-attribute conflict resolution). The evaluator gains entity-matching precision/recall/F1 vs gold labeled pairs and fusion accuracy vs gold fused records; the matching/fusion engines are protected alongside the evaluator, while the rule files stay loop-writable. Demonstrated arc: entity-matching F1 0→1.00 and fusion accuracy 0.875→1.00 across two approved cycles, each with no regression on the other.
- **Reference engagement: partner-data onboarding (`engagements/madi_onboarding/`).** The same generic loop, pointed at a `POST /ingest` service that maps + normalizes partner records to a canonical company schema via declarative per-source adapters, benchmarked on MaDI-Bench's Companies task. Onboarding a new source is measured against **held-out gold labels** (schema-mapping F1, value accuracy, fully-correct rate) — metrics that returning HTTP 200 cannot move. Includes a checksum-pinned downloader (data is CC BY-NC-ND, never committed), synthetic fixtures for tests, and a CASE_STUDY documenting a real 0%→100% onboarding across two approved cycles with no regression on the already-onboarded source.
- **Loop safety, generic to every engagement:** a second human gate (approve the exact tested patch after the app's `[app].evaluator` runs against held-out truth) and a deterministic protected-path allowlist (`scripts/check_protected_paths.py`) that rejects any implementer patch touching evaluators, gold, fixtures, or scoring — so the loop cannot improve its own metrics by editing what measures them.
- `flywheel_config` gains `[app].evaluator` and `[protected].paths` (default empty, so the calculator is unaffected).

### Changed
- **The loop can now drive more than one app.** `flywheel_config.py` selects its config via (in order) an explicit path, the `FLYWHEEL_CONFIG` environment variable, then the repo-root `flywheel.toml`. Sections absent from the built-in defaults (e.g. `[traffic]`) are preserved instead of being silently dropped, and path-valued keys (`app.usage_log`, `simulator.edge_cases`, `traffic.replay_file`) resolve against the config file's own directory so an engagement config refers to its own files. Non-path keys (`module`, `base_url`) are left untouched.
- `analyze_usage.py`: use `int | float` in `isinstance` (ruff UP038) — clears a lint failure that was breaking CI.

### Added
- `python scripts/flywheel_config.py --get SECTION.KEY` prints a single config value, so shell steps in the loop skills can read the active app module instead of hardcoding it.
- The loop skills (`/dev-loop`, `/simulate`) and the three planner agents (`feature-suggester`, `implementer`, `docs-updater`) now read the app module, base URL, and usage-log path from the active `flywheel.toml` via the `--get` accessor instead of hardcoding the calculator. Pointing the loop at another app is now a config edit, matching what CLAUDE.md already promised. The calculator loop is unchanged.
- `simulate.py --replay FILE` (and `[traffic].replay_file`) fires a fixed list of recorded request specs instead of synthesizing them, so a run is reproducible. Precedence: `--replay` flag > `[traffic].replay_file` > schema-random (unchanged default).
- Every simulated request now carries an `X-Run-Id` header (`--run-id`, else a random `sim-*` id); the middleware records it as `run_id`, so one run's traffic can be isolated in the shared usage log without renaming it.
- `[app].usage_log` config key; `app/main.py` reads its log path from the `USAGE_LOG_PATH` env var (default unchanged), which the loop's launcher exports from that key so server and analyzer agree on the file.
- Config, replay, and run-id tests (`tests/test_flywheel_config.py`, `tests/test_simulate.py`, and two cases in `tests/test_usage_logging.py`).

### Removed
- **`docs-updater` subagent**, with no replacement test. It produced OpenAPI `summary=`/`description=` strings nothing downstream reads — the simulator synthesizes requests from types/enums/schemas, never from prose. Adding a test to protect its output would enforce a convention with no consumer.
- **`edge_cases` capability**, protocol and code both: the required `EDGE_CASES:` implementer output, the merge step, `load_edge_cases()`, the `DOMAIN_EDGE_CASES` overlay in `simulate.py`, and the `[simulator].edge_cases` config key. No shipped config enabled it.
- **`scripts/analyze_usage.py`** and the generic `[app].analyzer` fallback. It keyed its per-operation breakdown on the deleted calculator's `operation` field, so its main report was already dead against the only shipped app — it was not generic, just undiscovered dead code. `[app].analyzer` is now required; each engagement supplies its own.
- **`feature-suggester` subagent.** Its isolation was nominal — the orchestrator writes its prompt and already holds its entire input — and its output was 2-3 sentences a human chooses between at Gate 1. Folded into `/dev-loop` STEP 2. The loop now has exactly one subagent, `implementer`, whose restriction is mechanical (no Bash).
- The `[signals]` config section (zero consumers anywhere in the codebase).

### Fixed
- **`check_protected_paths.py` failed open with no config resolved.** With no repo-root `flywheel.toml` (removed with the calculator) and `FLYWHEEL_CONFIG` unset, `[protected].paths` defaulted to `[]` and every patch passed — including one editing the held-out evaluator. It now refuses to run at all when no config resolves. A `FLYWHEEL_CONFIG` pointing at a nonexistent file now raises instead of silently falling back to defaults; an *implicit* missing config (no path argument, no env var set) stays permissive, which is `simulate.py`'s tested contract.
- **The guard was a step that could be skipped, not a gate.** `scripts/apply_patch.py` is now the single entry point that runs the protected-path guard, `git apply --check`, and `git apply`, in that fixed order; `.claude/settings.json` denies `Bash(git apply:*)` directly. Not an OS-level boundary — the orchestrator still holds Bash — but there is no longer a path that lands a patch without passing the guard first.
- **The protected-path guard's rename/copy detection was a ~60-line hand-rolled text parser** (`_git_unquote`, octal decoding, `_strip_prefix`) working around the fact that `git apply --numstat -z` collapses rename sources. Replaced with outright rejection of any patch containing `rename from`/`copy from`/`similarity index` — the implementer has no legitimate reason to rename or copy a file, and three lines of fail-closed rejection is safer than sixty lines of parse-then-check.
- **`evaluate.py`'s `_detect_regressions` and record lookup assumed value gold and a `record_id` always exist.** Both now degrade correctly for the real-data test split: `value_recall`/`fully_correct_rate` report `null` (not `0.0`) when no `gold_records.jsonl` is pinned, `_detect_regressions` skips a `None`-valued comparison instead of raising, and `evaluate_source` uses `rec.get("record_id")` since real MaDI-Bench CSVs carry no such column.
- **`to_replay.py` collapsed every record with no natural id into one telemetry bucket.** The server hashes `record.get("record_id")` for `record_id_hash`; records with none (all of them, for the real MaDI-Bench CSVs) all hashed identically, so the gap report showed "1 record" for every gap regardless of the real count (300). `to_specs()` now assigns an ordinal fallback id (`<source>-<i>`) when a record has none.

### Added
- **Held-out real-data test split.** `engagements/madi_onboarding/flywheel.real.toml` points the same loop at MaDI-Bench's own forbes/dbpedia/fullcontact CSVs and its own `sm_mapping_gold.json` (via `prepare_real_eval.py`) instead of the synthetic dev fixtures, through a separate `adapters_real/` write surface and `[app].target_schema`/`[app].adapters_dir` overrides (`app/main.py` now reads both from env, matching the existing `USAGE_LOG_PATH` pattern). Scored once, offline, never during a loop cycle — the mechanism that answers the score-delta probing channel a repeatedly-observed evaluator delta could otherwise open (see SECURITY.md). `runs/real_forbes/00_baseline` is the first receipt: 2000 real records, `schema_f1=0.0`/`integrated_rate=0.0` for the starting empty adapter, `value_recall`/`fully_correct_rate` correctly `null`.
- **`Read`/`Grep` deny on `runs/**`** — committed receipts are the converged answers to prior cycles; the implementer must not be able to read them.
- **`.claude/skills/dev-loop-trial/`** — a measurement mode that runs every `/dev-loop` control (guard, tests, evaluator, regression check) but auto-answers both human gates, reverts after every trial, and tags every artifact `"gates": "auto"`. For measuring how reliably the agent converges an empty real-data adapter, not for landing changes.
- **Evaluator-invocation budget as mechanism, not orchestrator prose.** `evaluate.py` appends one line per invocation to `$FLYWHEEL_EVAL_LOG` when set, so a trial's oracle-consultation count is an observable, not an assumption.
- **CI recomputes every committed `runs/forbes/` and `runs/reconcile/` receipt from its committed adapter/rule-TOML snapshot** and verifies every `*.diff` still hashes to its recorded `*.diff_hash.txt` — a stale receipt now fails CI instead of silently drifting from the engines that produced it.
- Tests for all of the above: guard fail-closed and `apply_edits.py` (`tests/test_apply_edits.py`, `tests/test_check_protected_paths.py`), `None`-metric and missing-`record_id` handling (`tests/test_madi_evaluate.py`), the eval-log budget (`tests/test_madi_evaluate_reconcile.py`), and the ordinal fallback id (`tests/test_to_replay.py`).

### Changed
- **The implementer returns structured edits, not a unified diff.** A 5-trial measurement run (`runs/trials/README.md`) found the implementer produced a malformed diff on 2/5 first attempts — an off-by-one hunk-header count and a wrong-context hunk. Both were hand-computed bookkeeping the model has no reliable way to get right without ever running `git diff` itself (it has no Bash). Its output is now a JSON list of `{"file", "old_string", "new_string"}` edits — the same contract this tool's own Edit/Write tools use — applied by the new `scripts/apply_edits.py`, which validates every edit's `old_string` matches the current file exactly once before writing anything (atomic: one bad edit rejects the whole submission). `scripts/check_protected_paths.py` is simplified to match: it checks each edit's `file` path directly instead of parsing `git apply --numstat -z` output, and the ~60 lines of rename/copy/symlink detection are gone outright — those are diff-format operations with no equivalent in the edit contract, so there is nothing left to detect. `scripts/apply_patch.py` is removed; `scripts/apply_edits.py` replaces it as the single guarded entry point.

## [0.5.0] - 2026-06-16

### Added
- Added safe_divide operation to /calculate and /calculate/batch endpoints that returns null result instead of HTTP 400 when b=0, enabling graceful null-handling in client code.

## [0.4.0] - 2026-06-16

### Added
- Added POST /calculate/batch endpoint that accepts a JSON array of {op, a, b} objects and returns per-item results in a single round-trip, isolating per-item errors (DivisionByZero, Overflow, NonFiniteInput) without aborting the batch.

### Changed
- Usage collection is now **endpoint-generic**: the middleware records every product endpoint (everything outside `SKIP_USAGE_PATHS`), not just `/calculate`. Records gain `path` and `method` fields and `inputs` now captures all query params. This closes the feedback loop for any feature shape — new endpoints' traffic becomes signal automatically.
- `analyze_usage.py` keys its breakdown by `op` for `/calculate` and by `path` for other endpoints, and adds a **Requested-but-missing endpoints (HTTP 404)** section so unmet demand surfaces as a build signal.
- Subagent handoffs now use standard unified diffs validated with `git apply --check` before application, replacing prose insertion points and ad hoc find/replace patching.
- The automated bonus now uses Claude Code's built-in `/loop /dev-loop` runtime runner; `/dev-loop` itself remains one complete, test-gated cycle.

### Added
- `tests/test_usage_logging.py` — functional TestClient tests asserting that product endpoints are recorded, unknown paths are captured as 404 signal, and infra endpoints (`/health`) are excluded.

### Fixed
- `usage_log.jsonl` is now gitignored and untracked (runtime artifact), matching its description in SETUP.md.

## [0.3.0] - 2026-06-16

### Added
- `abs` operation on `/calculate` computing `|a - b|` (absolute difference) — shipped via agentic dev-loop cycle 2 (suggested from 82 calls with negative a, 76 with negative b)

## [0.2.0] - 2026-06-16

### Added
- `mod` operation on `/calculate` computing `a % b` with HTTP 400 DivisionByZero guard when `b=0` — shipped via agentic dev-loop cycle 1 (suggested by feature-suggester from 2/129 calls returning HTTP 422 on op=modulo)
- Non-finite input rejection: `nan`/`inf`/`-inf` operands return HTTP 422 `NonFiniteInput`; overflowing results return HTTP 400 `Overflow`
- `source` field on usage records (from `X-Usage-Source` header) to separate simulator traffic from organic traffic
- `scripts/analyze_usage.py` — converts the raw log into a per-operation signal report consumed by the feature-suggester

### Changed
- feature-suggester now reads the analyze_usage.py report and skips already-implemented features (no more chasing stale signals)
- `/dev-loop` runs continuously (bonus): loops back automatically after each cycle; human approval is the only blocking step

### Fixed
- Tests no longer pollute `usage_log.jsonl` (`tests/conftest.py` redirects the log during the test session)
- `pytest tests/ -v` works via `pyproject.toml` `pythonpath` config
- Simulator fails loudly if `/openapi.json` has no `op` enum instead of silently using a hardcoded op list

## [0.1.0] - 2026-06-16

### Added
- Initial FastAPI calculator with add, subtract, multiply, divide operations
- Usage middleware recording timestamp, operation, inputs, status_code, latency_ms, error_type to usage_log.jsonl
- Schema-driven simulator skill (/simulate) that exercises all endpoints from /openapi.json
- Agentic dev-loop orchestrator (/dev-loop) with human approval gate
- feature-suggester, implementer, docs-updater subagents
