"""Turn source records into a replay file of POST /ingest calls.

Reuses the PR1 replay format (one JSON spec per line), so the generic simulator
fires them with `simulate.py --replay`. Each record becomes one ingest request;
`meta` carries the record id and source for auditing (not sent upstream).

Usage:
    python engagements/madi_onboarding/to_replay.py --source forbes
    python engagements/madi_onboarding/to_replay.py --source forbes --input data/forbes.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ENGAGEMENT_DIR = Path(__file__).resolve().parent


def to_specs(records: list[dict], source: str, schema_version: str = "v1"):
    for i, rec in enumerate(records):
        # A record with no natural id (e.g. the real MaDI-Bench CSVs) would all
        # hash to the same record_id_hash server-side, collapsing distinct
        # records into one bucket in the integration-gap report. Give it an
        # ordinal fallback id so telemetry can tell records apart.
        record = rec if "record_id" in rec else {**rec, "record_id": f"{source}-{i}"}
        yield {
            "method": "POST",
            "path": "/ingest",
            "query": {},
            "body": {"source_system": source, "schema_version": schema_version, "record": record},
            "meta": {"record_id": record.get("record_id"), "source": source},
        }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Build an /ingest replay file from source records")
    ap.add_argument("--source", required=True, help="source system name (e.g. forbes)")
    ap.add_argument("--input", default=None, help="source jsonl (default: fixtures/sources/<source>.jsonl)")
    ap.add_argument("--output", default=None, help="replay jsonl (default: <engagement>/replay_<source>.jsonl)")
    ap.add_argument("--schema-version", default="v1")
    args = ap.parse_args(argv)

    inp = Path(args.input) if args.input else ENGAGEMENT_DIR / "fixtures" / "sources" / f"{args.source}.jsonl"
    out = Path(args.output) if args.output else ENGAGEMENT_DIR / f"replay_{args.source}.jsonl"
    records = [json.loads(ln) for ln in inp.read_text().splitlines() if ln.strip()]

    with out.open("w") as f:
        for spec in to_specs(records, args.source, args.schema_version):
            f.write(json.dumps(spec) + "\n")
    print(f"Wrote {len(records)} ingest specs → {out}")


if __name__ == "__main__":
    main()
