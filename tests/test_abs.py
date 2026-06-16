"""Tests for the abs (absolute difference) operation: |a - b|."""


def test_abs_positive_order(client):
    r = client.get("/calculate", params={"op": "abs", "a": 5, "b": 3})
    assert r.status_code == 200
    assert r.json()["result"] == 2


def test_abs_reversed_order(client):
    r = client.get("/calculate", params={"op": "abs", "a": 3, "b": 5})
    assert r.status_code == 200
    assert r.json()["result"] == 2


def test_abs_negative_operand(client):
    r = client.get("/calculate", params={"op": "abs", "a": -4, "b": 3})
    assert r.status_code == 200
    assert r.json()["result"] == 7


def test_abs_result_never_negative(client):
    r = client.get("/calculate", params={"op": "abs", "a": -10, "b": -2})
    assert r.status_code == 200
    assert r.json()["result"] >= 0
    assert r.json()["result"] == 8


def test_abs_floats(client):
    r = client.get("/calculate", params={"op": "abs", "a": 2.5, "b": 4.0})
    assert r.status_code == 200
    assert r.json()["result"] == 1.5
