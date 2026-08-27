#!/usr/bin/env python3
"""Delivery telemetry for the loop itself: what one cycle cost, and what it bought.

The loop instruments the app it improves. This instruments the loop, so the
"controlled delivery" claim can be stated in numbers instead of adjectives: how
long a cycle takes, how much of that is a human standing at a gate, how often a
first submission is accepted, and how often a control actually fired.

The model never computes a duration or copies a metric across. It calls `mark`
at a phase boundary and this script stamps the clock; `finish` derives sizes and
metric deltas by reading the edits file and the evaluator JSON directly. Same
reasoning as the structured-edit contract: mechanical bookkeeping handed to a
model is where the malformed-diff failures came from, so it does not get handed
one here either.

    start   --cycle N [--gates human|auto] [--trial T]   begin, stamp t0
    mark    PHASE                                        stamp a phase boundary
    finish  --outcome OUTCOME [--edits F] [--evaluate F] [--baseline F]
    report  [--log F]                                    summary + headline economics

Durations are deltas between consecutive stamps, so phases are whatever the
caller marks. `mark implement` twice in one cycle is a resubmission, and is
counted as one — that is the retry signal, not an error.

What is deliberately NOT recorded: token cost. Claude Code does not hand a skill
a reliable per-subagent token count, and an invented number would undo the
credibility the rest of the receipts earn. Wall-clock and human gate latency are
measurable, so those are what get claimed.

The in-progress file is scratch (gitignored). The finished JSONL is committed
evidence, and sits under runs/ where the implementer cannot read it.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from flywheel_config import get_value

IN_PROGRESS = Path(".dev_loop_cycle.json")

# A cycle ends exactly one of these ways. Anything else is a typo, not a new
# outcome — an open vocabulary here would quietly split the same failure across
# two spellings and make the acceptance rate wrong.
OUTCOMES = (
    "kept",               # Gate 2 approved the tested change
    "reverted",           # Gate 2 declined it
    "regression-blocked", # evaluator reported regression: true — hard stop
    "tests-failed",       # pytest never went green
    "guard-rejected",     # protected-path guard refused the submission
    "validation-failed",  # old_string not found / not unique / bad create
    "skipped",            # Gate 1 declined to start
)

# Outcomes where a control stopped the cycle rather than a human choosing to.
CONTROL_STOPS = ("regression-blocked", "guard-rejected", "validation-failed", "tests-failed")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _read_state() -> dict:
    if not IN_PROGRESS.exists():
        raise SystemExit("no cycle in progress — run `cycle_log.py start` first")
    return json.loads(IN_PROGRESS.read_text())


def _write_state(state: dict) -> None:
    IN_PROGRESS.write_text(json.dumps(state, indent=2) + "\n")


def durations(marks: list[dict]) -> dict[str, float]:
    """Seconds per phase, summing repeats of the same phase (a resubmission adds
    to `implement` rather than replacing it)."""
    out: dict[str, float] = {}
    for i, m in enumerate(marks):
        prev = datetime.fromisoformat(marks[i - 1]["at"] if i else m["t0"])
        secs = (datetime.fromisoformat(m["at"]) - prev).total_seconds()
        out[m["phase"]] = round(out.get(m["phase"], 0.0) + secs, 2)
    return out


def edit_stats(edits_path: Path | None) -> dict:
    """Submission size, read from the implementer's own edits file."""
    if not edits_path or not edits_path.exists():
        return {"files": None, "edits": None, "bytes_changed": None}
    try:
        edits = json.loads(edits_path.read_text())
    except (OSError, json.JSONDecodeError):
        return {"files": None, "edits": None, "bytes_changed": None}
    if not isinstance(edits, list):
        return {"files": None, "edits": None, "bytes_changed": None}
    return {
        "files": len({e.get("file") for e in edits if isinstance(e, dict) and e.get("file")}),
        "edits": len(edits),
        "bytes_changed": sum(
            len(str(e.get("new_string", ""))) for e in edits if isinstance(e, dict)
        ),
    }


def _headline_metrics(evaluate: dict) -> dict[str, float]:
    """Flatten an evaluator result to {name: value} for the metrics that move.

    Only numeric leaves are kept, so a `null` value_recall (unmeasured on the
    real split) never becomes a 0.0 delta.
    """
    out: dict[str, float] = {}
    for source, m in (evaluate.get("per_source") or {}).items():
        for key, val in m.items():
            if isinstance(val, int | float) and not isinstance(val, bool):
                out[f"{source}.{key}"] = val
    rec = evaluate.get("reconcile") or {}
    if rec:
        out["reconcile.entity_matching_f1"] = rec.get("entity_matching", {}).get("f1")
        out["reconcile.fusion_accuracy"] = rec.get("fusion", {}).get("accuracy")
    return {k: v for k, v in out.items() if isinstance(v, int | float)}


def metric_deltas(evaluate_path: Path | None, baseline_path: Path | None) -> dict:
    """Per-metric before/after, derived from the two evaluator JSONs themselves."""
    def load(p: Path | None) -> dict:
        if not p or not p.exists():
            return {}
        try:
            return _headline_metrics(json.loads(p.read_text()))
        except (OSError, json.JSONDecodeError):
            return {}

    after, before = load(evaluate_path), load(baseline_path)
    return {
        k: {"before": before.get(k), "after": after[k], "delta": round(after[k] - before[k], 4)}
        for k in sorted(after)
        if isinstance(before.get(k), int | float) and after[k] != before[k]
    }


def eval_call_count(eval_log: Path | None) -> int | None:
    """How many times the oracle was consulted, from evaluate.py's own log."""
    if not eval_log or not eval_log.exists():
        return None
    return sum(1 for ln in eval_log.read_text().splitlines() if ln.strip())


def cmd_start(args) -> int:
    _write_state({
        "cycle": args.cycle,
        "trial": args.trial,
        "gates": args.gates,
        "config": str(get_value("app.module")),
        "t0": _now(),
        "marks": [],
    })
    print(f"cycle {args.cycle} started ({args.gates} gates)")
    return 0


def cmd_mark(args) -> int:
    state = _read_state()
    state["marks"].append({"phase": args.phase, "at": _now(), "t0": state["t0"]})
    _write_state(state)
    return 0


def cmd_finish(args) -> int:
    state = _read_state()
    marks = state["marks"]
    phases = durations(marks)
    record = {
        "timestamp": _now(),
        "cycle": state["cycle"],
        "trial": state["trial"],
        "gates": state["gates"],
        "app": state["config"],
        "outcome": args.outcome,
        "control_stop": args.outcome in CONTROL_STOPS,
        "seconds": phases,
        "total_seconds": round(sum(phases.values()), 2),
        "human_seconds": round(phases.get("gate1", 0.0) + phases.get("gate2", 0.0), 2),
        "resubmissions": max(0, sum(1 for m in marks if m["phase"] == "implement") - 1),
        "eval_calls": eval_call_count(Path(args.eval_log) if args.eval_log else None),
        **edit_stats(Path(args.edits) if args.edits else None),
        "metrics": metric_deltas(
            Path(args.evaluate) if args.evaluate else None,
            Path(args.baseline) if args.baseline else None,
        ),
    }

    log = Path(args.log or get_value("app.cycle_log"))
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as f:
        f.write(json.dumps(record) + "\n")
    IN_PROGRESS.unlink(missing_ok=True)

    print(f"cycle {record['cycle']}: {record['outcome']} in {record['total_seconds']}s "
          f"({record['human_seconds']}s at gates) → {log}")
    return 0


def summarize(records: list[dict]) -> dict:
    """Headline economics. Rates are over cycles that reached a decision, so a
    skipped cycle never inflates or deflates the acceptance rate."""
    decided = [r for r in records if r.get("outcome") != "skipped"]
    kept = [r for r in decided if r.get("outcome") == "kept"]
    n_kept = len(kept)
    return {
        "cycles": len(records),
        "decided": len(decided),
        "accepted": n_kept,
        "acceptance_rate": round(n_kept / len(decided), 4) if decided else None,
        "control_stops": sum(1 for r in decided if r.get("control_stop")),
        "resubmissions": sum(r.get("resubmissions") or 0 for r in decided),
        "first_pass_rate": (
            round(sum(1 for r in kept if not r.get("resubmissions")) / n_kept, 4) if n_kept else None
        ),
        "human_minutes_per_accepted": (
            round(sum(r.get("human_seconds") or 0 for r in decided) / n_kept / 60, 2) if n_kept else None
        ),
        "wall_minutes_per_accepted": (
            round(sum(r.get("total_seconds") or 0 for r in decided) / n_kept / 60, 2) if n_kept else None
        ),
        "eval_calls_per_accepted": (
            round(sum(r.get("eval_calls") or 0 for r in decided) / n_kept, 2) if n_kept else None
        ),
    }


def cmd_report(args) -> int:
    log = Path(args.log or get_value("app.cycle_log"))
    if not log.exists():
        print(f"No delivery telemetry yet at {log}. Run a cycle first.")
        return 0
    records = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
    if not records:
        print(f"No cycles recorded in {log}.")
        return 0

    s = summarize(records)
    print("── Delivery economics ──────────────────────────────────")
    print(f"  cycles recorded            {s['cycles']}  ({s['decided']} reached a decision)")
    print(f"  accepted at Gate 2         {s['accepted']}  ({(s['acceptance_rate'] or 0) * 100:.0f}%)")
    print(f"  stopped by a control       {s['control_stops']}")
    print(f"  resubmissions              {s['resubmissions']}")
    if s["first_pass_rate"] is not None:
        print(f"  accepted on first pass     {s['first_pass_rate'] * 100:.0f}%")
    if s["human_minutes_per_accepted"] is not None:
        print(f"  human min / accepted       {s['human_minutes_per_accepted']}")
        print(f"  wall min / accepted        {s['wall_minutes_per_accepted']}")
        print(f"  evaluator calls / accepted {s['eval_calls_per_accepted']}")
    print()
    print("── Per cycle ───────────────────────────────────────────")
    for r in records:
        tag = f"trial {r['trial']} " if r.get("trial") else ""
        moved = ", ".join(f"{k} {m['before']}→{m['after']}" for k, m in (r.get("metrics") or {}).items())
        print(f"  {tag}cycle {r['cycle']:<3} {r['outcome']:<18} "
              f"{r['total_seconds']:>7.1f}s  gates {r['human_seconds']:>6.1f}s  {moved}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Record and report the loop's own delivery cost")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("start", help="begin a cycle")
    p.add_argument("--cycle", type=int, required=True)
    p.add_argument("--gates", choices=("human", "auto"), default="human")
    p.add_argument("--trial", type=int, default=None)
    p.set_defaults(fn=cmd_start)

    p = sub.add_parser("mark", help="stamp a phase boundary")
    p.add_argument("phase", help="e.g. simulate, analyze, gate1, implement, apply, test, evaluate, gate2")
    p.set_defaults(fn=cmd_mark)

    p = sub.add_parser("finish", help="close the cycle and append one record")
    p.add_argument("--outcome", choices=OUTCOMES, required=True)
    p.add_argument("--edits", default=None, help="the implementer's edits JSON, for submission size")
    p.add_argument("--evaluate", default=None, help="this cycle's evaluator JSON")
    p.add_argument("--baseline", default=None, help="the pre-cycle evaluator JSON")
    p.add_argument("--eval-log", default=None, help="$FLYWHEEL_EVAL_LOG for this cycle")
    p.add_argument("--log", default=None)
    p.set_defaults(fn=cmd_finish)

    p = sub.add_parser("report", help="print the summary")
    p.add_argument("--log", default=None)
    p.set_defaults(fn=cmd_report)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
