from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_mod_positive_integers():
    response = client.get("/calculate", params={"op": "mod", "a": 10, "b": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == 1.0
    assert data["op"] == "mod"
    assert data["a"] == 10.0
    assert data["b"] == 3.0


def test_mod_negative_dividend():
    response = client.get("/calculate", params={"op": "mod", "a": -10, "b": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == -10 % 3  # Python semantics: 2.0


def test_mod_negative_divisor():
    response = client.get("/calculate", params={"op": "mod", "a": 10, "b": -3})
    assert response.status_code == 200
    data = response.json()
    assert data["result"] == 10 % -3  # Python semantics: -2.0


def test_mod_by_zero_returns_400():
    response = client.get("/calculate", params={"op": "mod", "a": 5, "b": 0})
    assert response.status_code == 400
    data = response.json()
    assert data["error_type"] == "DivisionByZero"
    assert "zero" in data["error"].lower()
