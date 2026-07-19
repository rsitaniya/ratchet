"""Engagement analyzer: turn structured ingest telemetry into ranked gaps.

Reads the integration events the ingest app writes and produces the signal the
feature-suggester cites: per-source integration rate, and integration gaps ranked
by how many distinct records each one affects. This is the domain-aware analyzer
for this engagement; the generic scripts/analyze_usage.py stays HTTP-level and is
untouched (the de-hardcoded feature-suggester is pointed at this one instead).

Usage:
    python engagements/madi_onboarding/analyze_integration.py [LOG] [--source S] [--run-id R]
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def _load(path: str) -> list[dict]:
    try:
        text = Path(path).read_text()
    except FileNotFoundError:
        return []
    return [json.loads(ln) for ln in text.splitlines() if ln.strip()]


def summarize(rows: list[dict], source: str | None = None, run_id: str | None = None) -> dict:
    def keep(r):
        return (source is None or r.get("source_system") == source) and (
            run_id is None or r.get("run_id") == run_id
        )

    sources: dict[str, dict] = defaultdict(lambda: {"records": 0, "integrated": 0})
    gap_records: dict[tuple, set] = defaultdict(set)

    for r in rows:
        if not keep(r):
            continue
        if r.get("event") == "record":
            s = sources[r["source_system"]]
            s["records"] += 1
            if r.get("integrated"):
                s["integrated"] += 1
        elif r.get("event") == "integration":
            key = (r["source_system"], r["error_code"], r.get("field"))
            gap_records[key].add(r.get("record_id_hash"))

    for s in sources.values():
        s["integrated_rate"] = round(s["integrated"] / s["records"], 4) if s["records"] else 0.0

    gaps = [
        {"source_system": src, "error_code": code, "field": field, "affected_records": len(hashes)}
        for (src, code, field), hashes in gap_records.items()
    ]
    gaps.sort(key=lambda g: g["affected_records"], reverse=True)
    return {"sources": dict(sources), "gaps": gaps}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Rank onboarding gaps from integration telemetry")
    ap.add_argument("log_path", nargs="?", default="usage_log.jsonl")
    ap.add_argument("--source", default=None)
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)

    report = summarize(_load(args.log_path), args.source, args.run_id)
    if not report["sources"]:
        print(f"No integration telemetry in {args.log_path}. Replay some traffic first.")
        return

    print("── Integration status by source ────────────────────────")
    for src, s in sorted(report["sources"].items(), key=lambda kv: kv[1]["integrated_rate"]):
        print(f"  {src:<14} {s['integrated']}/{s['records']} integrated ({s['integrated_rate'] * 100:.1f}%)")
    print()
    print("── Top integration gaps (rank by affected records) ─────")
    if not report["gaps"]:
        print("  (none)")
    for g in report["gaps"][:15]:
        print(f"  {g['affected_records']:>4} records  {g['error_code']:<22} {g['source_system']}.{g['field']}")


if __name__ == "__main__":
    main()
