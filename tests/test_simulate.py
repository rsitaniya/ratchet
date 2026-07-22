"""Unit tests for the simulator's replay mode and argument handling.

The live firing path (httpx → running server) is exercised end-to-end by the CI
loop-closure job in schema mode, which shares the same fire() code. These tests
pin the new decision logic — traffic-source precedence, replay parsing, the
fire-each-spec glue — and the backward-compatible positional interface the
dev-loop skill and CI depend on (`simulate.py BASE_URL N`).
"""
import json

import simulate


def test_positional_args_still_parse():
    args = simulate.parse_args(["http://localhost:8000", "30"])
    assert args.base_url == "http://localhost:8000"
    assert args.n_requests == 30
    assert args.replay is None


def test_replay_and_run_id_flags_parse():
    args = simulate.parse_args(["http://x:8000", "--replay", "r.jsonl", "--run-id", "rt-1"])
    assert args.replay == "r.jsonl"
    assert args.run_id == "rt-1"


def test_resolve_replay_path_cli_wins():
    config = {"traffic": {"replay_file": "/from/config.jsonl"}}
    assert simulate.resolve_replay_path("/from/cli.jsonl", config) == "/from/cli.jsonl"


def test_resolve_replay_path_config_fallback():
    config = {"traffic": {"replay_file": "/from/config.jsonl"}}
    assert simulate.resolve_replay_path(None, config) == "/from/config.jsonl"


def test_resolve_replay_path_none_means_schema_mode():
    assert simulate.resolve_replay_path(None, {"traffic": {"replay_file": ""}}) is None
    assert simulate.resolve_replay_path(None, {}) is None


def test_load_replay_specs_parses_and_skips_blanks(tmp_path):
    f = tmp_path / "replay.jsonl"
    f.write_text(
        json.dumps({"method": "POST", "path": "/requests/mortgage", "body": {}}) + "\n"
        "\n"  # blank line skipped
        + json.dumps({"method": "GET", "path": "/requests/unknown"}) + "\n"
    )
    specs = simulate.load_replay_specs(str(f))
    assert [s["path"] for s in specs] == ["/requests/mortgage", "/requests/unknown"]


def test_effective_parameters_merges_path_level_and_resolves_ref():
    root = {"components": {"parameters": {"Item": {"name": "item_id", "in": "path", "schema": {"type": "integer"}}}}}
    path_item = {"parameters": [{"$ref": "#/components/parameters/Item"}]}
    op_spec = {"parameters": [{"name": "q", "in": "query", "schema": {"type": "string"}}]}
    params = simulate.effective_parameters(op_spec, path_item, root)
    by = {(p["name"], p["in"]) for p in params}
    assert ("item_id", "path") in by  # path-level, $ref-resolved
    assert ("q", "query") in by       # operation-level


def test_operation_param_overrides_path_level_by_name_and_location():
    path_item = {"parameters": [{"name": "id", "in": "path", "schema": {"type": "string"}}]}
    op_spec = {"parameters": [{"name": "id", "in": "path", "schema": {"type": "integer"}}]}
    params = simulate.effective_parameters(op_spec, path_item, {})
    assert len(params) == 1 and params[0]["schema"]["type"] == "integer"


def test_build_request_substitutes_declared_path_param():
    params = [{"name": "item_id", "in": "path", "schema": {"type": "integer"}}]
    filled, qp, body = simulate.build_request("/items/{item_id}", {}, params, {})
    assert "{item_id}" not in filled and filled.startswith("/items/")


def test_build_request_fills_undeclared_path_var():
    # A templated path with no declared parameter must not fire a literal "{id}".
    filled, _, _ = simulate.build_request("/items/{item_id}", {}, [], {})
    assert filled == "/items/1"


def test_allof_generates_every_branch_property():
    root = {}
    schema = {"allOf": [
        {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]},
        {"type": "object", "properties": {"b": {"type": "string"}}, "required": ["b"]},
    ]}
    val = simulate.gen_value(schema, root)
    assert set(val) == {"a", "b"}  # both branches, not just the first


def test_discover_carries_path_level_params():
    schema = {"paths": {"/items/{item_id}": {
        "parameters": [{"name": "item_id", "in": "path", "schema": {"type": "integer"}}],
        "get": {"responses": {}},
    }}}
    ops = simulate.discover(schema)
    assert len(ops) == 1
    _path, _method, _spec, params = ops[0]
    assert params and params[0]["name"] == "item_id"


def test_run_replay_fires_each_spec_in_order_with_run_id(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(
        simulate,
        "fire",
        lambda base_url, method, path, params, body, label, idx, stats, run_id: calls.append(
            (method, path, run_id)
        ),
    )
    f = tmp_path / "replay.jsonl"
    f.write_text(
        json.dumps({"method": "POST", "path": "/requests/mortgage", "body": {"x": 1}}) + "\n"
        + json.dumps({"method": "POST", "path": "/requests/credit-card"}) + "\n"
    )
    simulate.run_replay("http://localhost:8000", str(f), "rt-9")
    assert calls == [
        ("post", "/requests/mortgage", "rt-9"),
        ("post", "/requests/credit-card", "rt-9"),
    ]
