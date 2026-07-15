#!/usr/bin/env python3
"""
Usage analytics — turns usage_log.jsonl into actionable product signal.

Reads the append-only usage log and prints a per-endpoint/operation breakdown:
call volume, error rate, error-type distribution, likely-unsupported operations
(100% HTTP 422), requested-but-missing endpoints (HTTP 404 — "build this"), and
input-distribution signals. Rows are keyed by `operation` where present and by
`path` otherwise, so a brand-new endpoint's traffic becomes signal automatically.
This is the report the feature-suggester reads to ground its proposals.

Which request params get profiled under "Input signals" comes from [signals] in
flywheel.toml, so this report carries no domain knowledge of its own. Configure
nothing and every section except that one still works.

Usage:
    python scripts/analyze_usage.py [LOG_PATH] [--last N] [--source SOURCE]

Defaults: LOG_PATH=usage_log.jsonl, analyzes all entries from all sources.
"""
import argparse
import json
from collections import Counter, defaultdict

from flywheel_config import load_config

CONFIG = load_config()
NUMERIC_PARAMS: list[str] = CONFIG["signals"]["numeric_params"]
ZERO_VALUE_PARAMS: list[str] = CONFIG["signals"]["zero_value_params"]


def load(path: str, last: int | None, source: str | None) -> list[dict]:
    rows: list[dict] = []
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        return []
    if source:
        rows = [r for r in rows if (r.get("source") or "unknown") == source]
    if last is not None:
        rows = rows[-last:]
    return rows


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def main() -> None:
    ap = argparse.ArgumentParser(description="Analyze usage_log.jsonl")
    ap.add_argument("log_path", nargs="?", default="usage_log.jsonl")
    ap.add_argument("--last", type=int, default=None, help="Analyze only the last N entries")
    ap.add_argument("--source", default=None, help="Filter to one source (e.g. simulator)")
    args = ap.parse_args()

    rows = load(args.log_path, args.last, args.source)
    total = len(rows)
    if total == 0:
        print(f"No usage data in {args.log_path}. Run the simulator first.")
        return

    per_op: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "errors": 0, "latency": [], "error_types": Counter()}
    )
    sources: Counter = Counter()
    missing: Counter = Counter()  # paths requested but not implemented (HTTP 404)
    zero_counts: Counter = Counter()  # configured param -> times it was 0
    neg_counts: Counter = Counter()  # configured param -> times it was negative

    for e in rows:
        # Key by op where the endpoint reports one, by path otherwise.
        # New endpoints (and old op-only records) both slot in cleanly.
        op = e.get("operation") or e.get("path") or "<none>"
        s = per_op[op]
        s["calls"] += 1
        status = e.get("status_code", 0)
        if status >= 400:
            s["errors"] += 1
            s["error_types"][e.get("error_type") or f"HTTP{status}"] += 1
        if status == 404 and e.get("path"):
            missing[e["path"]] += 1
        lat = e.get("latency_ms")
        if isinstance(lat, (int, float)):
            s["latency"].append(lat)
        sources[e.get("source") or "unknown"] += 1
        inp = e.get("inputs", {}) or {}
        for name in NUMERIC_PARAMS:
            val = _to_float(inp.get(name))
            if val is not None and val < 0:
                neg_counts[name] += 1
        for name in ZERO_VALUE_PARAMS:
            if _to_float(inp.get(name)) == 0:
                zero_counts[name] += 1

    window = f"last {args.last}" if args.last else "all entries"
    src_filter = f"  |  Source filter: {args.source}" if args.source else ""
    print(f"Usage Analysis — {args.log_path}")
    print(f"Total requests: {total}  |  Window: {window}{src_filter}")
    print()

    print("── Per-endpoint / operation ────────────────────────────")
    print(f"  {'op / path':<16}{'calls':>7}{'errors':>8}{'error%':>9}{'avg_ms':>9}")
    for op, s in sorted(per_op.items(), key=lambda kv: -kv[1]["calls"]):
        err_pct = s["errors"] / s["calls"] * 100 if s["calls"] else 0
        avg = sum(s["latency"]) / len(s["latency"]) if s["latency"] else 0
        print(f"  {op:<16}{s['calls']:>7}{s['errors']:>8}{err_pct:>8.1f}%{avg:>8.2f}")
    print()

    print("── Error breakdown ─────────────────────────────────────")
    if any(s["errors"] for s in per_op.values()):
        for op, s in per_op.items():
            for et, n in s["error_types"].items():
                print(f"  {op}: {et} × {n} ({n / s['calls'] * 100:.1f}% of {op} calls)")
    else:
        print("  (no errors)")
    print()

    print("── Likely-unsupported operations (100% HTTP 422) ───────")
    flagged = [
        (op, s["calls"])
        for op, s in per_op.items()
        if s["calls"] > 0 and s["error_types"].get("HTTP422", 0) == s["calls"]
    ]
    if flagged:
        for op, n in flagged:
            print(f"  op='{op}': {n} calls ({n / total * 100:.1f}% of total) — all failed HTTP 422")
    else:
        print("  (none)")
    print()

    print("── Requested-but-missing endpoints (HTTP 404) ──────────")
    if missing:
        for path, n in missing.most_common():
            print(f"  {path}: {n} requests to a path that doesn't exist — candidate new endpoint")
    else:
        print("  (none)")
    print()

    print("── Input signals ───────────────────────────────────────")
    if not NUMERIC_PARAMS and not ZERO_VALUE_PARAMS:
        print("  (no params configured — set [signals] in flywheel.toml to profile inputs)")
    for name in ZERO_VALUE_PARAMS:
        n = zero_counts[name]
        print(f"  {f'{name}=0 inputs:':<15}{n:>5} ({n / total * 100:.1f}% of total)")
    for name in NUMERIC_PARAMS:
        print(f"  {f'negative {name}:':<15}{neg_counts[name]:>5}")
    print(f"  {'sources:':<15}{dict(sources)}")


if __name__ == "__main__":
    main()
