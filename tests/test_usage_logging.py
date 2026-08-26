"""Functional tests for the endpoint-generic usage-collection mechanism.

These hit the app via TestClient and assert on the "http"-event records the
middleware writes, proving the mechanism itself works for any endpoint shape —
not the domain-specific "integration"/"record" events /ingest also emits. The
usage log is redirected to a temp file by tests/conftest.py, so these read
`engagements.madi_onboarding.app.main.USAGE_LOG` rather than the real signal.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

import engagements.madi_onboarding.app.main as m
from engagements.madi_onboarding.app.main import app

client = TestClient(app)

FIX = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "fixtures"


def _rows(name):
    return [json.loads(ln) for ln in (FIX / "sources" / name).read_text().splitlines() if ln.strip()]


def _records() -> list[dict]:
    if not m.USAGE_LOG.exists():
        return []
    return [json.loads(line) for line in m.USAGE_LOG.read_text().splitlines() if line.strip()]


def test_ingest_traffic_is_recorded():
    rec = _rows("dbpedia.jsonl")[0]
    client.post("/ingest", json={"source_system": "dbpedia", "record": rec})
    recs = [r for r in _records() if r.get("path") == "/ingest"]
    assert recs, "expected /ingest traffic to be recorded"
    assert recs[-1]["status_code"] == 200
    assert recs[-1]["method"] == "POST"


def test_unknown_endpoint_is_recorded_as_signal():
    # A request to an endpoint that doesn't exist yet IS product signal:
    # "someone wanted this — build it." It must be captured, not dropped.
    client.get("/nonexistent")
    recs = [r for r in _records() if r.get("path") == "/nonexistent"]
    assert recs, "expected unknown-endpoint traffic to be recorded as signal"
    assert recs[-1]["status_code"] == 404


def test_health_is_not_recorded_as_signal():
    client.get("/health")
    recs = [r for r in _records() if r.get("path") == "/health"]
    assert recs == [], "infra endpoints must not pollute product signal"


def test_run_id_header_is_recorded():
    # The X-Run-Id header lets one replay run be isolated from another when
    # measuring before/after, without renaming the shared server-owned log.
    rec = _rows("dbpedia.jsonl")[0]
    client.post("/ingest", json={"source_system": "dbpedia", "record": rec}, headers={"X-Run-Id": "run-42"})
    recs = [r for r in _records() if r.get("path") == "/ingest" and r.get("run_id") == "run-42"]
    assert recs, "expected the run_id header to be recorded on the usage record"


def test_run_id_absent_is_null():
    rec = _rows("dbpedia.jsonl")[0]
    client.post("/ingest", json={"source_system": "dbpedia", "record": rec})
    recs = [r for r in _records() if r.get("path") == "/ingest"]
    assert "run_id" in recs[-1], "run_id field must always be present"
    assert recs[-1]["run_id"] is None, "run_id defaults to null when the header is absent"


def test_concurrent_requests_produce_well_formed_usage_log():
    # The write path is a single `.open("a")` + one `.write()` per record — a
    # POSIX append is atomic under PIPE_BUF, so concurrent writers must never
    # interleave into a corrupt or dropped line. Prove it under real thread
    # concurrency rather than trusting the POSIX guarantee by inspection alone.
    n = 60
    run_id = "concurrency-test"
    rec = _rows("dbpedia.jsonl")[0]

    def _fire(i):
        return client.post("/ingest", json={"source_system": "dbpedia", "record": rec}, headers={"X-Run-Id": run_id})

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(_fire, range(n)))
    assert all(r.status_code == 200 for r in results)

    # _records() itself raises on any line that fails json.loads, so reaching
    # this assert already proves every written line parsed cleanly. Filter to
    # the "http" event: /ingest also emits a domain "record" event per call,
    # which carries no run_id field to match on.
    recs = [r for r in _records() if r.get("path") == "/ingest" and r.get("run_id") == run_id]
    assert len(recs) == n, f"expected {n} well-formed log lines, found {len(recs)}"


def test_logging_failure_does_not_break_the_request(tmp_path, monkeypatch):
    # If the usage log cannot be written (here: the path is a directory), the
    # served request must still succeed — telemetry is fail-open, not fatal.
    a_dir = tmp_path / "not-a-file"
    a_dir.mkdir()
    monkeypatch.setattr(m, "USAGE_LOG", a_dir)
    rec = _rows("dbpedia.jsonl")[0]
    r = client.post("/ingest", json={"source_system": "dbpedia", "record": rec})
    assert r.status_code == 200
    assert r.json()["integrated"] is True
