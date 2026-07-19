"""Tests for the Stage 2 reconcile evaluator (EM F1 + fusion accuracy)."""
from pathlib import Path

from engagements.madi_onboarding import evaluate as E

ENG = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding"
FIX = ENG / "fixtures"

CONVERGED_MATCH = """threshold = 0.88
blocking_key = "country"
[[compare]]
field = "name"
similarity = "jaro_winkler"
weight = 0.7
[[compare]]
field = "city"
similarity = "exact"
weight = 0.3
"""

CONVERGED_FUSION = """default_strategy = "prefer_source"
source_priority = ["acme_crm", "vendor_erp"]
[attributes.revenue]
strategy = "prefer_source"
source_priority = ["vendor_erp", "acme_crm"]
"""


def test_seed_state_low_matching_partial_fusion():
    # With the committed seed rules: exact-name matching finds nothing (F1 0),
    # naive fusion gets 7/8 attributes right (revenue wrong on all 5 entities).
    r = E.evaluate_reconcile(FIX)
    assert r["entity_matching"]["f1"] == 0.0
    assert r["fusion"]["accuracy"] == round(35 / 40, 4)  # 5 entities * 7/8 correct


def test_converged_rules_reach_perfect(tmp_path):
    m = tmp_path / "m.toml"
    f = tmp_path / "f.toml"
    m.write_text(CONVERGED_MATCH)
    f.write_text(CONVERGED_FUSION)
    r = E.evaluate_reconcile(FIX, matching_rules_path=m, fusion_rules_path=f)
    assert r["entity_matching"]["f1"] == 1.0
    assert r["entity_matching"]["precision"] == 1.0
    assert r["entity_matching"]["recall"] == 1.0
    assert r["fusion"]["accuracy"] == 1.0


def test_reconcile_regression_detected():
    baseline = {"reconcile": {"entity_matching": {"f1": 1.0}, "fusion": {"accuracy": 1.0}}}
    current = {"reconcile": {"entity_matching": {"f1": 0.5}, "fusion": {"accuracy": 1.0}}}
    assert "entity_matching" in E._detect_regressions(current, baseline)
    assert "fusion" not in E._detect_regressions(current, baseline)


def test_main_includes_reconcile(capsys):
    import json
    E.main([])
    out = json.loads(capsys.readouterr().out)
    assert "reconcile" in out
    assert set(out["reconcile"]) == {"entity_matching", "fusion"}
