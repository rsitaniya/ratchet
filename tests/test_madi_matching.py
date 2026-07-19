"""Tests for the pure entity-matching engine."""
import json
from pathlib import Path

from engagements.madi_onboarding import matching as M

FIX = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "fixtures" / "reconcile"
SEED_RULES = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "matching_rules.toml"


def _rows(name):
    return [json.loads(ln) for ln in (FIX / name).read_text().splitlines() if ln.strip()]


def _gold():
    return {(p["left_id"], p["right_id"]) for p in _rows("gold_pairs.jsonl")}


CONVERGED = {
    "threshold": 0.88,
    "blocking_key": "country",
    "compare": [
        {"field": "name", "similarity": "jaro_winkler", "weight": 0.7},
        {"field": "city", "similarity": "exact", "weight": 0.3},
    ],
}


def test_seed_rules_match_nothing():
    left, right = _rows("left.jsonl"), _rows("right.jsonl")
    rules = M.load_rules(SEED_RULES)  # exact name, names differ across sources
    assert M.match(left, right, rules) == []


def test_converged_rules_recover_all_gold_pairs_exactly():
    left, right = _rows("left.jsonl"), _rows("right.jsonl")
    predicted = set(M.match(left, right, CONVERGED))
    assert predicted == _gold()  # precision AND recall = 1.0, no false matches


def test_blocking_prevents_cross_country_false_matches():
    # L6 (CA) and R7 (IN) share no country with any true partner → never matched.
    left, right = _rows("left.jsonl"), _rows("right.jsonl")
    predicted = set(M.match(left, right, CONVERGED))
    matched_left = {lid for lid, _ in predicted}
    assert "L6" not in matched_left
    assert all(rid != "R7" for _, rid in predicted)


def test_missing_rules_file_matches_nothing(tmp_path):
    rules = M.load_rules(tmp_path / "nope.toml")
    assert M.match(_rows("left.jsonl"), _rows("right.jsonl"), rules) == []


def test_score_pair_is_weighted_average():
    left = {"name": "Acme", "city": "NY"}
    right = {"name": "Acme", "city": "LA"}
    compares = [
        {"field": "name", "similarity": "exact", "weight": 0.5},
        {"field": "city", "similarity": "exact", "weight": 0.5},
    ]
    assert M.score_pair(left, right, compares) == 0.5  # name matches, city doesn't
