"""Functional tests for the /reconcile endpoint and its signal."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import engagements.madi_onboarding.app.main as m
from engagements.madi_onboarding import analyze_integration as AI

FIX = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "fixtures" / "reconcile"


def _rows(name):
    return [json.loads(ln) for ln in (FIX / name).read_text().splitlines() if ln.strip()]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "USAGE_LOG", tmp_path / "usage.jsonl")
    return TestClient(m.app)


def _events(client):
    return [json.loads(ln) for ln in m.USAGE_LOG.read_text().splitlines() if ln.strip()] if m.USAGE_LOG.exists() else []


def _post(client):
    return client.post("/reconcile", json={
        "left_source": "acme_crm", "right_source": "vendor_erp",
        "left": _rows("left.jsonl"), "right": _rows("right.jsonl"),
    }, headers={"X-Run-Id": "rec-1"})


def test_bad_source_name_is_rejected_at_boundary(client):
    # An unsafe source name must be a 422 at the API boundary, not a path traversal.
    r = client.post("/reconcile", json={
        "left_source": "../../etc/passwd", "right_source": "vendor_erp", "left": [], "right": [],
    })
    assert r.status_code == 422


def test_oversized_reconcile_input_is_rejected(client):
    big = [{"record_id": f"L{i}", "country": "US"} for i in range(5001)]
    r = client.post("/reconcile", json={
        "left_source": "acme_crm", "right_source": "vendor_erp", "left": big, "right": [],
    })
    assert r.status_code == 422


def test_seed_rules_match_nothing_all_unmatched(client):
    # Committed matching_rules.toml is the weak seed (exact name) → 0 matches.
    body = _post(client).json()
    assert body["matched"] == []
    assert len(body["unmatched_left"]) == 6 and len(body["unmatched_right"]) == 6


def test_reconcile_signal_reports_match_gap(client):
    _post(client)
    summary = AI.summarize_reconcile(_events(client), run_id="rec-1")
    assert summary["match_rate"] == 0.0
    assert summary["matched"] == 0 and summary["unmatched"] == 12


def test_telemetry_is_privacy_preserving(client):
    _post(client)
    blob = json.dumps(_events(client))
    assert "Nimbus" not in blob and "L1" not in blob  # only hashes + field names


def test_reconcile_conflict_signal_after_matching(client, tmp_path, monkeypatch):
    # Point the app at converged matching rules so pairs match and fusion
    # conflicts (name, revenue) surface as ranked signal.
    rules = tmp_path / "m.toml"
    rules.write_text(
        'threshold = 0.88\nblocking_key = "country"\n'
        '[[compare]]\nfield = "name"\nsimilarity = "jaro_winkler"\nweight = 0.7\n'
        '[[compare]]\nfield = "city"\nsimilarity = "exact"\nweight = 0.3\n'
    )
    monkeypatch.setattr(matching_module(), "RULES_PATH", rules)
    _post(client)
    summary = AI.summarize_reconcile(_events(client), run_id="rec-1")
    assert summary["matched"] == 5
    fields = {c["field"] for c in summary["attribute_conflicts"]}
    assert "name" in fields and "revenue" in fields  # the two seeded conflicts


def matching_module():
    from engagements.madi_onboarding import matching
    return matching
