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
