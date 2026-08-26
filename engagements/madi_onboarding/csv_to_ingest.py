"""Convert a downloaded MaDI-Bench source CSV into the raw-record JSONL shape
`to_replay.py` and `POST /ingest` expect: one JSON object per row, columns
verbatim.

Pure format translation — no MaDI-specific field knowledge. Which raw column
means what is exactly the problem the onboarding adapter (`adapters/<source>.toml`)
solves; this script only gets a partner's CSV export into JSON so the loop has
something to onboard. It works on any of MaDI-Bench's Companies sources (or any
other CSV with a header row) without per-source special-casing.

Usage:
    uv run python engagements/madi_onboarding/download_data.py       # fetch data/forbes.csv etc.
    uv run python engagements/madi_onboarding/csv_to_ingest.py --source forbes
    uv run python engagements/madi_onboarding/to_replay.py --source forbes \\
        --input engagements/madi_onboarding/data/forbes.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ENGAGEMENT_DIR = Path(__file__).resolve().parent
DATA_DIR = ENGAGEMENT_DIR / "data"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Convert a MaDI-Bench source CSV to ingest-ready JSONL")
    ap.add_argument("--source", default=None, help="source system name (e.g. forbes); reads data/<source>.csv")
    ap.add_argument("--input", default=None, help="source csv (default: data/<source>.csv)")
    ap.add_argument("--output", default=None, help="output jsonl (default: data/<source>.jsonl)")
    args = ap.parse_args(argv)
    if not args.source and not (args.input and args.output):
        ap.error("--source is required unless both --input and --output are given")

    inp = Path(args.input) if args.input else DATA_DIR / f"{args.source}.csv"
    out = Path(args.output) if args.output else DATA_DIR / f"{args.source}.jsonl"

    with inp.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit(f"{inp}: no data rows (empty or header-only CSV)")

    # CSV cells become JSON string values as-is — an empty cell becomes "",
    # which similarity.is_absent() and the adapter engine already treat as
    # absent — so the adapter under test sees exactly what the source shipped.
    with out.open("w") as f:
        for rec in rows:
            f.write(json.dumps(rec) + "\n")
    print(f"Wrote {len(rows)} records → {out}")


if __name__ == "__main__":
    main()
