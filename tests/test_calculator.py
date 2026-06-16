import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_add_integers():
    r = client.get("/calculate", params={"op": "add", "a": 3, "b": 4})
    assert r.status_code == 200
    assert r.json()["result"] == 7.0


def test_subtract():
    r = client.get("/calculate", params={"op": "subtract", "a": 10, "b": 3})
    assert r.status_code == 200
    assert r.json()["result"] == 7.0


def test_multiply():
    r = client.get("/calculate", params={"op": "multiply", "a": 3, "b": 4})
    assert r.status_code == 200
    assert r.json()["result"] == 12.0


def test_divide():
    r = client.get("/calculate", params={"op": "divide", "a": 10, "b": 2})
    assert r.status_code == 200
    assert r.json()["result"] == 5.0


def test_divide_by_zero_returns_400():
    r = client.get("/calculate", params={"op": "divide", "a": 7, "b": 0})
    assert r.status_code == 400
    assert r.json()["error_type"] == "DivisionByZero"


def test_negative_operands():
    r = client.get("/calculate", params={"op": "multiply", "a": -3, "b": 4})
    assert r.status_code == 200
    assert r.json()["result"] == -12.0


def test_float_operands():
    r = client.get("/calculate", params={"op": "add", "a": 1.5, "b": 2.5})
    assert r.status_code == 200
    assert r.json()["result"] == pytest.approx(4.0)


def test_large_numbers():
    r = client.get("/calculate", params={"op": "multiply", "a": 1e9, "b": 1e9})
    assert r.status_code == 200
    assert r.json()["result"] == pytest.approx(1e18)


def test_response_contains_inputs():
    r = client.get("/calculate", params={"op": "add", "a": 5, "b": 6})
    body = r.json()
    assert body["a"] == 5.0
    assert body["b"] == 6.0
    assert body["op"] == "add"


def test_invalid_op_returns_422():
    r = client.get("/calculate", params={"op": "modulo", "a": 5, "b": 3})
    assert r.status_code == 422


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
