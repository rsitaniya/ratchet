"""Build a fixture-shaped view of the real MaDI-Bench Companies data under
data/madi/, so evaluate.py can score real forbes/dbpedia/fullcontact records
against the benchmark's own schema-matching gold — with no new loader.

This is the real-data **test** split: synthetic fixtures/ stays the loop's dev
split (fast, deterministic, scored every cycle at Gate 2); data/madi/ is scored
only when this script's output is explicitly pointed at (flywheel.real.toml),
and the loop never sees it during an ordinary cycle.

This script legitimately reads real gold (sm_mapping_gold.json) to build
gold_mapping.json — that is its whole job, the same way evaluate.py's own
author had to see the synthetic gold_records.jsonl's shape to write the
scorer in the first place. It is PROTECTED (`[protected].paths` in
flywheel.real.toml): the implementer must never run or edit it, and its
output already matches the existing `**/gold_*.json` deny glob, so it needs
no new protection rule.

Only sm_mapping_gold.json is pinned for the real benchmark — no normalized-
value gold. So this produces target_schema.json and gold_mapping.json, but no
gold_records.jsonl; evaluate.py treats that absence as "no value gold for this
source" and reports value_recall / fully_correct_rate as null, never 0.0 (0.0
would misrepresent "unmeasured" as "totally wrong").

Preconditions: run download_data.py, then csv_to_ingest.py --source <name>
for each source you want scored.

Usage:
    uv run python engagements/madi_onboarding/prepare_real_eval.py
"""
from __future__ import annotations

import json
from pathlib import Path

ENGAGEMENT_DIR = Path(__file__).resolve().parent
DATA_DIR = ENGAGEMENT_DIR / "data"
OUT_DIR = DATA_DIR / "madi"

SOURCES = ("forbes", "dbpedia", "fullcontact")


def build_target_schema() -> dict:
    """Flatten MaDI's JSON-Schema target into the engagement's own
    {"attributes": {name: {"required": bool}}} shape (see fixtures/target_schema.json
    for the shape evaluate.py and adapters.py already read)."""
    raw = json.loads((DATA_DIR / "target_schema.json").read_text())
    required = set(raw.get("required", []))
    return {
        "attributes": {
            name: {"required": name in required}
            for name in raw.get("properties", {})
        }
    }


def build_gold_mapping() -> dict[str, dict[str, str]]:
    """{source: {source_column: target_column}} from sm_mapping_gold.json's
    positive correspondences (label == True) — the same shape as the
    synthetic fixtures/gold_mapping.json that evaluate.py's _f1() reads."""
    raw = json.loads((DATA_DIR / "sm_mapping_gold.json").read_text())
    out: dict[str, dict[str, str]] = {}
    for row in raw.get("mappings", []):
        if not row.get("label"):
            continue
        src = row["source_dataset"]
        out.setdefault(src, {})[row["source_column"]] = row["target_column"]
    return out


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "target_schema.json").write_text(json.dumps(build_target_schema(), indent=2) + "\n")
    (OUT_DIR / "gold_mapping.json").write_text(json.dumps(build_gold_mapping(), indent=2) + "\n")

    sources_dir = OUT_DIR / "sources"
    sources_dir.mkdir(exist_ok=True)
    written, skipped = [], []
    for name in SOURCES:
        jsonl = DATA_DIR / f"{name}.jsonl"
        if jsonl.exists():
            (sources_dir / f"{name}.jsonl").write_text(jsonl.read_text())
            written.append(name)
        else:
            skipped.append(name)

    print(f"Wrote real-data fixture view to {OUT_DIR}")
    print(f"  sources ready: {written or '(none)'}")
    if skipped:
        print(f"  sources missing (run download_data.py, then csv_to_ingest.py --source <name>): {skipped}")
    print("No value gold is pinned for the real benchmark: value_recall and")
    print("fully_correct_rate will report null for these sources (see evaluate.py).")


if __name__ == "__main__":
    main()
