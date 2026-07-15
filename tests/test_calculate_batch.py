from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def post_batch(items):
    return client.post("/calculate/batch", json=items)


def test_basic_add():
    r = post_batch([{"op": "add", "a": 3, "b": 4}])
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 1
    assert data[0]["result"] == 7.0
    assert data[0]["op"] == "add"
    assert data[0]["error"] is None
    assert data[0]["error_type"] is None


def test_multiple_ops_in_order():
    items = [
        {"op": "add", "a": 1, "b": 2},
        {"op": "subtract", "a": 10, "b": 3},
        {"op": "multiply", "a": 4, "b": 5},
        {"op": "divide", "a": 9, "b": 3},
        {"op": "mod", "a": 10, "b": 3},
        {"op": "abs", "a": 2, "b": 7},
    ]
    r = post_batch(items)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 6
    assert data[0]["result"] == 3.0
    assert data[1]["result"] == 7.0
    assert data[2]["result"] == 20.0
    assert data[3]["result"] == 3.0
    assert data[4]["result"] == 1.0
    assert data[5]["result"] == 5.0


def test_division_by_zero_does_not_abort_batch():
    items = [
        {"op": "add", "a": 1, "b": 2},
        {"op": "divide", "a": 1, "b": 0},
        {"op": "multiply", "a": 3, "b": 3},
    ]
    r = post_batch(items)
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 3
    assert data[0]["result"] == 3.0
    assert data[1]["error_type"] == "DivisionByZero"
    assert data[1]["result"] is None
    assert data[2]["result"] == 9.0


def test_mod_by_zero():
    r = post_batch([{"op": "mod", "a": 5, "b": 0}])
    assert r.status_code == 200
    data = r.json()
    assert data[0]["error_type"] == "DivisionByZero"
    assert data[0]["result"] is None


def test_overflow_does_not_abort_batch():
    items = [
        {"op": "multiply", "a": 1e308, "b": 1e308},
        {"op": "add", "a": 1, "b": 1},
    ]
    r = post_batch(items)
    assert r.status_code == 200
    data = r.json()
    assert data[0]["error_type"] == "Overflow"
    assert data[0]["result"] is None
    assert data[1]["result"] == 2.0


def test_invalid_operand_type_returns_422():
    r = post_batch([{"op": "add", "a": "not_a_number", "b": 1}])
    assert r.status_code == 422


def test_empty_batch():
    r = post_batch([])
    assert r.status_code == 200
    assert r.json() == []


def test_invalid_op_returns_422():
    r = post_batch([{"op": "power", "a": 2, "b": 3}])
    assert r.status_code == 422


def test_response_length_matches_request_length():
    items = [{"op": "add", "a": i, "b": i} for i in range(10)]
    r = post_batch(items)
    assert r.status_code == 200
    assert len(r.json()) == 10
