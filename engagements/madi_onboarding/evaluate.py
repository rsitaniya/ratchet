"""PROTECTED held-out evaluator — the semantic oracle for the onboarding loop.

This scores an adapter set against gold labels the loop is NOT allowed to see or
edit: gold field correspondences (schema-matching F1) and gold normalized records
(value recall, fully-correct rate). It reads the source files, applies the current
adapters, and compares to gold — it never reads the telemetry log, and the
orchestrator forbids the implementer from editing this file, the mapping engine it
runs (`adapters.py`), the fixtures, or the gold. So its verdict is independent of
the telemetry and of the gold labels; the loop can still add adapter data and new
normalizers, but neither can inflate the score (gold is unreachable and a wrong
normalizer only lowers it).

The implementer subagent is forbidden to modify this file, the fixtures, or the
gold (enforced by the orchestrator's protected-path allowlist). That is what
stops the loop from "improving" by weakening its own test.

Metrics (none satisfiable by returning HTTP 200):
  - schema_f1          : F1 of predicted vs gold field correspondences
  - value_recall       : recall of gold values — share of gold attribute values
                         the adapters reproduce exactly (denominator is gold)
  - integrated_rate    : share of records with all required attributes produced
  - fully_correct_rate : share of records whose every gold attribute matches

Usage:
    python engagements/madi_onboarding/evaluate.py [--baseline FILE] [--sources a,b]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Run directly as `python .../evaluate.py` (as documented above), a script has
# no package context, so the absolute import below can't resolve even with the
# project installed — put the repo root on sys.path first. `-m` and normal
# imports already have __package__ set and skip this.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from engagements.madi_onboarding import adapters as A

ENGAGEMENT_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = ENGAGEMENT_DIR / "fixtures"
ADAPTERS_DIR = ENGAGEMENT_DIR / "adapters"


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def _f1(predicted: dict[str, str], gold: dict[str, str]) -> float:
    if not gold:
        return 0.0
    correct = sum(1 for k, v in predicted.items() if gold.get(k) == v)
    precision = correct / len(predicted) if predicted else 0.0
    recall = correct / len(gold)
    return 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)


def evaluate_source(source: str, fixtures_dir: Path, adapters_dir: Path) -> dict:
    target_schema = json.loads((fixtures_dir / "target_schema.json").read_text())
    gold_mapping = json.loads((fixtures_dir / "gold_mapping.json").read_text()).get(source, {})
    gold_records = {g["record_id"]: g for g in _load_jsonl(fixtures_dir / "gold_records.jsonl")}
    records = _load_jsonl(fixtures_dir / "sources" / f"{source}.jsonl")
    adapter = A.load_adapter(source, adapters_dir)

    predicted = {sf: spec["target"] for sf, spec in adapter.get("fields", {}).items()}
    schema_f1 = _f1(predicted, gold_mapping)

    n = len(records)
    integrated = 0
    fully_correct = 0
    correct_values = 0
    total_values = 0
    for rec in records:
        res = A.apply_adapter(rec, adapter, target_schema)
        if res["integrated"]:
            integrated += 1
        gold = {k: v for k, v in gold_records.get(rec["record_id"], {}).items() if k != "record_id"}
        rec_all_correct = bool(gold)
        for attr, gold_val in gold.items():
            total_values += 1
            if res["target"].get(attr) == gold_val:
                correct_values += 1
            else:
                rec_all_correct = False
        if res["integrated"] and rec_all_correct:
            fully_correct += 1

    return {
        "source": source,
        "records": n,
        "schema_f1": round(schema_f1, 4),
        # Recall of gold values: correct ÷ number of gold attribute values.
        "value_recall": round(correct_values / total_values, 4) if total_values else 0.0,
        "integrated_rate": round(integrated / n, 4) if n else 0.0,
        "fully_correct_rate": round(fully_correct / n, 4) if n else 0.0,
    }


def evaluate(sources: list[str], fixtures_dir: Path = FIXTURES_DIR, adapters_dir: Path = ADAPTERS_DIR) -> dict:
    per_source = {s: evaluate_source(s, fixtures_dir, adapters_dir) for s in sources}
    return {"per_source": per_source}


def evaluate_reconcile(
    fixtures_dir: Path = FIXTURES_DIR,
    matching_rules_path: Path | None = None,
    fusion_rules_path: Path | None = None,
    left_source: str = "acme_crm",
    right_source: str = "vendor_erp",
) -> dict:
    """Stage 2 oracle: entity-matching F1 vs gold pairs, fusion accuracy vs gold.

    Fusion is scored on the GOLD-matched clusters so the fusion metric is isolated
    from matching quality. Both read gold the loop can't touch.
    """
    from engagements.madi_onboarding import fusion, matching

    rec = fixtures_dir / "reconcile"
    left = _load_jsonl(rec / "left.jsonl")
    right = _load_jsonl(rec / "right.jsonl")
    gold_pairs = {(p["left_id"], p["right_id"]) for p in _load_jsonl(rec / "gold_pairs.jsonl")}
    gold_fused = {g["entity"]: g for g in _load_jsonl(rec / "gold_fused.jsonl")}
    target_attrs = list(json.loads((fixtures_dir / "target_schema.json").read_text())["attributes"])

    # --- entity matching ---
    predicted = set(matching.match(left, right, matching.load_rules(matching_rules_path)))
    tp = len(predicted & gold_pairs)
    precision = tp / len(predicted) if predicted else 0.0
    recall = tp / len(gold_pairs) if gold_pairs else 0.0
    f1 = 0.0 if precision + recall == 0 else 2 * precision * recall / (precision + recall)

    # --- data fusion (on gold-matched clusters) ---
    frules = fusion.load_rules(fusion_rules_path)
    left_by = {r["record_id"]: r for r in left}
    right_by = {r["record_id"]: r for r in right}
    correct = total = 0
    for lid, rid in gold_pairs:
        cluster = [
            {"source": left_source, "record": left_by[lid]},
            {"source": right_source, "record": right_by[rid]},
        ]
        fused = fusion.fuse(cluster, frules, target_attrs)
        gold = {k: v for k, v in gold_fused[lid].items() if k != "entity"}
        for attr, gold_val in gold.items():
            total += 1
            if fused.get(attr) == gold_val:
                correct += 1

    return {
        "entity_matching": {
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "predicted": len(predicted), "gold": len(gold_pairs),
        },
        "fusion": {"accuracy": round(correct / total, 4) if total else 0.0},
    }


def _detect_regressions(current: dict, baseline: dict) -> list[str]:
    """A previously-supported source or capability regresses if its headline metric drops."""
    regressions = []
    for source, base in baseline.get("per_source", {}).items():
        cur = current.get("per_source", {}).get(source)
        if cur and cur["fully_correct_rate"] < base["fully_correct_rate"]:
            regressions.append(source)
    b_rec, c_rec = baseline.get("reconcile"), current.get("reconcile")
    if b_rec and c_rec:
        if c_rec["entity_matching"]["f1"] < b_rec["entity_matching"]["f1"]:
            regressions.append("entity_matching")
        if c_rec["fusion"]["accuracy"] < b_rec["fusion"]["accuracy"]:
            regressions.append("fusion")
    return regressions


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Evaluate onboarding adapters against gold")
    ap.add_argument("--sources", default="dbpedia,forbes", help="comma-separated source systems")
    ap.add_argument("--adapters", default=str(ADAPTERS_DIR))
    ap.add_argument("--fixtures", default=str(FIXTURES_DIR))
    ap.add_argument("--baseline", default=None, help="prior evaluate.py JSON to detect regressions against")
    args = ap.parse_args(argv)

    result = evaluate(
        [s.strip() for s in args.sources.split(",") if s.strip()],
        Path(args.fixtures), Path(args.adapters),
    )
    # Stage 2 reconcile metrics, when the reconcile fixtures are present.
    if (Path(args.fixtures) / "reconcile" / "gold_pairs.jsonl").exists():
        result["reconcile"] = evaluate_reconcile(Path(args.fixtures))
    if args.baseline:
        baseline = json.loads(Path(args.baseline).read_text())
        regressions = _detect_regressions(result, baseline)
        result["regressions"] = regressions
        result["regression"] = bool(regressions)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
