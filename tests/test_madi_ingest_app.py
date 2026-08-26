"""Functional tests for the ingest app via TestClient, including telemetry."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import engagements.madi_onboarding.app.main as m

FIX = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "fixtures"


def _rows(name):
    return [json.loads(ln) for ln in (FIX / "sources" / name).read_text().splitlines() if ln.strip()]


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(m, "USAGE_LOG", tmp_path / "usage.jsonl")
    return TestClient(m.app)


def _events(client):
    p = m.USAGE_LOG
    if not p.exists():
        return []
    return [json.loads(ln) for ln in p.read_text().splitlines() if ln.strip()]


def test_seeded_source_integrates_200(client):
    rec = _rows("dbpedia.jsonl")[0]
    r = client.post("/ingest", json={"source_system": "dbpedia", "record": rec}, headers={"X-Run-Id": "t1"})
    assert r.status_code == 200
    body = r.json()
    assert body["integrated"] is True
    assert body["target"]["name"] == "Nimbus Robotics"
    assert body["target"]["revenue"] == 480000000


def test_unonboarded_source_fails_422_with_structured_signal(client):
    rec = _rows("forbes.jsonl")[0]
    r = client.post("/ingest", json={"source_system": "forbes", "record": rec}, headers={"X-Run-Id": "t2"})
    assert r.status_code == 422
    codes = {f["error_code"] for f in r.json()["failures"]}
    assert "UNMAPPED_FIELD" in codes and "MISSING_REQUIRED_FIELD" in codes


def test_telemetry_is_structured_and_privacy_preserving(client):
    rec = _rows("forbes.jsonl")[0]
    client.post("/ingest", json={"source_system": "forbes", "record": rec}, headers={"X-Run-Id": "t3"})
    evs = _events(client)
    integ = [e for e in evs if e["event"] == "integration"]
    recs = [e for e in evs if e["event"] == "record"]
    assert integ and recs
    assert recs[0]["integrated"] is False
    # run_id propagates; raw id and raw values are never logged
    assert all(e["run_id"] == "t3" for e in integ)
    blob = json.dumps(evs)
    assert rec["record_id"] not in blob  # only the hash
    assert "Nimbus" not in blob  # no raw customer values in telemetry
    assert all("field" in e and "error_code" in e for e in integ)


def test_duplicate_record_id_is_processed_independently_each_time(client):
    # No idempotency/dedup check on /ingest — two requests carrying the same
    # record_id are each scored on their own merits, not rejected or collapsed.
    # This is current behavior, not a crash risk; analyze_integration.py's
    # gap-ranking dedup (a set keyed on record_id_hash) is the layer where a
    # repeated id actually changes a number — see test_madi_analyze.py.
    rec = _rows("dbpedia.jsonl")[0]
    r1 = client.post("/ingest", json={"source_system": "dbpedia", "record": rec}, headers={"X-Run-Id": "dup1"})
    r2 = client.post("/ingest", json={"source_system": "dbpedia", "record": rec}, headers={"X-Run-Id": "dup2"})
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json() == r2.json()


def test_health_not_logged(client):
    client.get("/health")
    assert [e for e in _events(client) if e.get("path") == "/health"] == []
