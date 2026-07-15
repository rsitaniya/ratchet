import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_safe_divide_normal_division():
    """safe_divide with b != 0 returns numeric result like regular divide."""
    r = client.get("/calculate", params={"op": "safe_divide", "a": 10, "b": 2})
    assert r.status_code == 200
    assert r.json()["result"] == 5.0


def test_safe_divide_by_zero_returns_null():
    """safe_divide with b=0 returns status 200 with result=null, not HTTP 400."""
    r = client.get("/calculate", params={"op": "safe_divide", "a": 7, "b": 0})
    assert r.status_code == 200
    assert r.json()["result"] is None


def test_safe_divide_by_zero_preserves_inputs():
    """safe_divide result=null response includes original a, b, op."""
    r = client.get("/calculate", params={"op": "safe_divide", "a": 100, "b": 0})
    assert r.status_code == 200
    body = r.json()
    assert body["result"] is None
    assert body["a"] == 100.0
    assert body["b"] == 0.0
    assert body["op"] == "safe_divide"


def test_safe_divide_negative_dividend():
    """safe_divide handles negative dividends normally."""
    r = client.get("/calculate", params={"op": "safe_divide", "a": -10, "b": 2})
    assert r.status_code == 200
    assert r.json()["result"] == -5.0


def test_safe_divide_negative_divisor():
    """safe_divide handles negative divisors normally."""
    r = client.get("/calculate", params={"op": "safe_divide", "a": 10, "b": -2})
    assert r.status_code == 200
    assert r.json()["result"] == -5.0


def test_safe_divide_both_negative():
    """safe_divide with both operands negative."""
    r = client.get("/calculate", params={"op": "safe_divide", "a": -10, "b": -2})
    assert r.status_code == 200
    assert r.json()["result"] == 5.0


def test_safe_divide_float_result():
    """safe_divide with float inputs/result."""
    r = client.get("/calculate", params={"op": "safe_divide", "a": 7.5, "b": 2.5})
    assert r.status_code == 200
    assert r.json()["result"] == pytest.approx(3.0)


def test_safe_divide_batch():
    """safe_divide works in batch endpoint, returning null for b=0 items."""
    body = [
        {"op": "safe_divide", "a": 10, "b": 2},
        {"op": "safe_divide", "a": 7, "b": 0},
        {"op": "safe_divide", "a": -15, "b": 3},
    ]
    r = client.post("/calculate/batch", json=body)
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 3

    # First item: normal division
    assert results[0]["result"] == 5.0
    assert results[0]["error"] is None

    # Second item: b=0, should have null result and no error
    assert results[1]["result"] is None
    assert results[1]["error"] is None
    assert results[1]["error_type"] is None

    # Third item: normal division
    assert results[2]["result"] == -5.0
    assert results[2]["error"] is None
