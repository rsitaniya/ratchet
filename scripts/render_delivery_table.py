#!/usr/bin/env python3
"""Render the delivery economics table into a doc, or check the one that is there.

The numbers a reader trusts most are the ones nobody retyped. This replaces a
hand-maintained markdown table with a generated one, so the published figures
cannot drift from `[app].cycle_log` at all -- the same reasoning as the
structured-edit contract, applied to prose: remove the transcription step rather
than validate it afterwards.

The doc marks the region; this script owns its contents:

    <!-- delivery-economics:start -->
    ...generated table...
    <!-- delivery-economics:end -->

    --write   regenerate the region in place
    --check   fail (exit 1) if the region is not what would be generated now

Domain-free: it reads whatever `cycle_log.summarize` reports for the active
config's log and takes the doc path as an argument, so it carries no knowledge of
any particular engagement.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from cycle_log import summarize
from flywheel_config import get_value

START = "<!-- delivery-economics:start -->"
END = "<!-- delivery-economics:end -->"


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value * 100:.0f}%"


def render(records: list[dict]) -> str:
    """The table body, derived only from the committed records."""
    s = summarize(records)
    kept = [r for r in records if r.get("outcome") == "kept"]
    eval_calls = s["eval_calls_per_accepted"]

    rows = [
        ("Cycles recorded / accepted at Gate 2",
         f"{s['cycles']} / {s['accepted']} ({_pct(s['acceptance_rate'])})"),
        ("Accepted on first pass",
         f"{_pct(s['first_pass_rate'])} ({s['resubmissions']} resubmissions)"),
        ("Stopped by a control", str(s["control_stops"])),
        ("Agent minutes per accepted change", str(s["agent_minutes_per_accepted"])),
        ("Wall minutes per accepted change (incl. gates)", str(s["wall_minutes_per_accepted"])),
        # Never 0: an unset --eval-log means the count was not taken, which is a
        # different fact from a measured zero.
        ("Evaluator calls per accepted change",
         "not measured (`--eval-log` was not set this run)" if eval_calls is None else str(eval_calls)),
    ]
    out = ["| Reported | Value |", "|---|---|"]
    out += [f"| {label} | {value} |" for label, value in rows]

    if kept:
        out += ["", "| Cycle | Outcome | Wall time | Agent time | Metrics moved |", "|---|---|---|---|---|"]
        for r in records:
            moved = ", ".join(
                f"`{k}` {m['before']} → {m['after']}" for k, m in (r.get("metrics") or {}).items()
            ) or "—"
            out.append(
                f"| {r['cycle']} | {r['outcome']} | {r['total_seconds']:.1f}s "
                f"| {r.get('agent_seconds', 0.0):.1f}s | {moved} |"
            )
    return "\n".join(out)


def splice(text: str, body: str) -> str:
    """Replace the marked region's contents, leaving the markers in place."""
    if START not in text or END not in text:
        raise SystemExit(f"doc has no {START} / {END} region")
    head, rest = text.split(START, 1)
    _, tail = rest.split(END, 1)
    return f"{head}{START}\n{body}\n{END}{tail}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("doc", help="markdown file containing the marked region")
    ap.add_argument("--log", default=None, help="cycle log (default: [app].cycle_log)")
    mode = ap.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)

    log = Path(args.log or get_value("app.cycle_log"))
    if not log.exists():
        print(f"no delivery telemetry at {log}", file=sys.stderr)
        return 1
    records = [json.loads(ln) for ln in log.read_text().splitlines() if ln.strip()]
    if not records:
        print(f"no cycles recorded in {log}", file=sys.stderr)
        return 1

    doc = Path(args.doc)
    current = doc.read_text()
    updated = splice(current, render(records))
    if args.write:
        doc.write_text(updated)
        print(f"wrote delivery economics into {doc}")
        return 0
    if updated != current:
        print(f"{doc} delivery-economics region is stale — regenerate it:", file=sys.stderr)
        print(f"  uv run python scripts/render_delivery_table.py {doc} --write", file=sys.stderr)
        return 1
    print(f"{doc} delivery economics match {log}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
