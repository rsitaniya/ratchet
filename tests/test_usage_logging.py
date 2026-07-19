"""Functional tests for the endpoint-generic usage-collection mechanism.

These hit the app via TestClient and assert on the records the middleware
writes, proving the loop self-feeds for ANY endpoint shape — not just /calculate
ops. The usage log is redirected to a temp file by tests/conftest.py, so these
read `app.main.USAGE_LOG` rather than the real product signal.
"""
import json

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
