"""Tests for non-finite input rejection and overflow handling."""


def test_nan_input_rejected(client):
    r = client.get("/calculate", params={"op": "add", "a": "nan", "b": 1})
    assert r.status_code == 422
    assert r.json()["error_type"] == "NonFiniteInput"


def test_inf_input_rejected(client):
    r = client.get("/calculate", params={"op": "add", "a": "inf", "b": 1})
    assert r.status_code == 422
    assert r.json()["error_type"] == "NonFiniteInput"


def test_negative_inf_input_rejected(client):
    r = client.get("/calculate", params={"op": "multiply", "a": "-inf", "b": 2})
    assert r.status_code == 422
    assert r.json()["error_type"] == "NonFiniteInput"


def test_overflow_literal_input_rejected(client):
    # 1e309 parses to inf as a Python float
    r = client.get("/calculate", params={"op": "add", "a": "1e309", "b": 0})
    assert r.status_code == 422
    assert r.json()["error_type"] == "NonFiniteInput"


def test_overflow_result_returns_400(client):
    # 1e308 * 1e308 overflows to inf despite finite inputs
    r = client.get("/calculate", params={"op": "multiply", "a": "1e308", "b": "1e308"})
    assert r.status_code == 400
    assert r.json()["error_type"] == "Overflow"
