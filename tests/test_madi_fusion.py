"""Tests for the pure data-fusion engine."""
import json
from pathlib import Path

from engagements.madi_onboarding import fusion as F

ENG = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding"
FIX = ENG / "fixtures" / "reconcile"
SEED_RULES = ENG / "fusion_rules.toml"
ATTRS = ["name", "founded", "country", "city", "industry", "assets", "revenue", "keypeople"]


def _load(name):
    return [json.loads(ln) for ln in (FIX / name).read_text().splitlines() if ln.strip()]


def _by_id(name, key="record_id"):
    return {r[key]: r for r in _load(name)}


def _gold_fused():
    return {g["entity"]: g for g in _load("gold_fused.jsonl")}


def _cluster(left_rec, right_rec):
    return [{"source": "acme_crm", "record": left_rec}, {"source": "vendor_erp", "record": right_rec}]


def test_seed_rules_get_name_right_but_revenue_wrong():
    left, right = _by_id("left.jsonl"), _by_id("right.jsonl")
    gold = _gold_fused()
    rules = F.load_rules(SEED_RULES)
    fused = F.fuse(_cluster(left["L1"], right["R1"]), rules, ATTRS)
    assert fused["name"] == gold["L1"]["name"]        # acme_crm's clean name — correct
    assert fused["revenue"] != gold["L1"]["revenue"]  # took acme_crm's stale revenue — wrong


def test_converged_rules_match_gold_fused_exactly():
    left, right = _by_id("left.jsonl"), _by_id("right.jsonl")
    gold = _gold_fused()
    converged = {
        "default_strategy": "prefer_source",
        "source_priority": ["acme_crm", "vendor_erp"],
        "attributes": {
            "revenue": {"strategy": "prefer_source", "source_priority": ["vendor_erp", "acme_crm"]},
        },
    }
    for lid, rid in [("L1", "R1"), ("L2", "R2"), ("L3", "R3"), ("L4", "R4"), ("L5", "R5")]:
        fused = F.fuse(_cluster(left[lid], right[rid]), converged, ATTRS)
        expected = {k: v for k, v in gold[lid].items() if k != "entity"}
        assert fused == expected, lid


def test_strategies():
    cl = [
        {"source": "a", "record": {"x": "short", "n": 5, "lst": ["p"]}},
        {"source": "b", "record": {"x": "much longer", "n": 9, "lst": ["p", "q"]}},
    ]
    assert F._apply("longest", cl, "x", []) == "much longer"
    assert F._apply("max", cl, "n", []) == 9
    assert F._apply("min", cl, "n", []) == 5
    assert F._apply("union", cl, "lst", []) == ["p", "q"]
    assert F._apply("prefer_source", cl, "x", ["b", "a"]) == "much longer"


def test_missing_rules_takes_first_source():
    rules = F.load_rules(Path("/does/not/exist.toml"))
    cl = [{"source": "a", "record": {"name": "First"}}, {"source": "b", "record": {"name": "Second"}}]
    assert F.fuse(cl, rules, ["name"])["name"] == "First"
