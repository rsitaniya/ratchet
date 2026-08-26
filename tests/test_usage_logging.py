"""Functional tests for the endpoint-generic usage-collection mechanism.

These hit the app via TestClient and assert on the records the middleware
writes, proving the loop self-feeds for ANY endpoint shape — not just /calculate
ops. The usage log is redirected to a temp file by tests/conftest.py, so these
read `app.main.USAGE_LOG` rather than the real product signal.
"""
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

import app.main as m
from app.main import app

client = TestClient(app)


def _records() -> list[dict]:
    if not m.USAGE_LOG.exists():
        return []
    return [json.loads(line) for line in m.USAGE_LOG.read_text().splitlines() if line.strip()]


def test_calculate_traffic_is_recorded():
    client.get("/calculate", params={"op": "add", "a": 1, "b": 2})
    recs = [r for r in _records() if r.get("path") == "/calculate"]
    assert recs, "expected /calculate traffic to be recorded"
    assert recs[-1]["operation"] == "add"
    assert recs[-1]["status_code"] == 200
    assert recs[-1]["method"] == "GET"


def test_unknown_endpoint_is_recorded_as_signal():
    # A request to an endpoint that doesn't exist yet IS product signal:
    # "someone wanted this — build it." It must be captured, not dropped.
    client.get("/sqrt", params={"a": 9})
    recs = [r for r in _records() if r.get("path") == "/sqrt"]
    assert recs, "expected unknown-endpoint traffic to be recorded as signal"
    assert recs[-1]["status_code"] == 404


def test_health_is_not_recorded_as_signal():
    client.get("/health")
    recs = [r for r in _records() if r.get("path") == "/health"]
    assert recs == [], "infra endpoints must not pollute product signal"


def test_run_id_header_is_recorded():
    # The X-Run-Id header lets one replay run be isolated from another when
    # measuring before/after, without renaming the shared server-owned log.
    client.get("/calculate", params={"op": "add", "a": 1, "b": 2}, headers={"X-Run-Id": "run-42"})
    recs = [r for r in _records() if r.get("run_id") == "run-42"]
    assert recs, "expected the run_id header to be recorded on the usage record"


def test_run_id_absent_is_null():
    client.get("/calculate", params={"op": "subtract", "a": 5, "b": 1})
    recs = [r for r in _records() if r.get("path") == "/calculate"]
    assert "run_id" in recs[-1], "run_id field must always be present"
    assert recs[-1]["run_id"] is None, "run_id defaults to null when the header is absent"


def test_concurrent_requests_produce_well_formed_usage_log():
    # The write path is a single `.open("a")` + one `.write()` per record — a
    # POSIX append is atomic under PIPE_BUF, so concurrent writers must never
    # interleave into a corrupt or dropped line. Prove it under real thread
    # concurrency rather than trusting the POSIX guarantee by inspection alone.
    n = 60
    run_id = "concurrency-test"

    def _fire(i):
        return client.get("/calculate", params={"op": "add", "a": i, "b": 1}, headers={"X-Run-Id": run_id})

    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(_fire, range(n)))
    assert all(r.status_code == 200 for r in results)

    # _records() itself raises on any line that fails json.loads, so reaching
    # this assert already proves every written line parsed cleanly.
    recs = [r for r in _records() if r.get("run_id") == run_id]
    assert len(recs) == n, f"expected {n} well-formed log lines, found {len(recs)}"


def test_logging_failure_does_not_break_the_request(tmp_path, monkeypatch):
    # If the usage log cannot be written (here: the path is a directory), the
    # served request must still succeed — telemetry is fail-open, not fatal.
    a_dir = tmp_path / "not-a-file"
    a_dir.mkdir()
    monkeypatch.setattr(m, "USAGE_LOG", a_dir)
    r = client.get("/calculate", params={"op": "add", "a": 1, "b": 2})
    assert r.status_code == 200
    assert r.json()["result"] == 3.0
