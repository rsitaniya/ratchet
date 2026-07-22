"""Unit tests for the config layer that lets one loop drive many apps.

flywheel_config was originally written for a single repo-root config. These
tests pin the multi-app behavior:
  - unknown sections (e.g. [traffic]) survive instead of being dropped,
  - path-valued keys resolve against the config file's own directory,
  - non-path keys (module, base_url) are left untouched,
  - $FLYWHEEL_CONFIG and an explicit path argument both select the config.
"""
import json

import flywheel_config


def _write_config(tmp_path, body: str):
    cfg = tmp_path / "flywheel.toml"
    cfg.write_text(body)
    return cfg


def test_missing_config_returns_defaults(tmp_path):
    # An absent config file is a supported mode, not an error.
    cfg = tmp_path / "nope.toml"
    conf = flywheel_config.load_config(cfg)
    assert conf["app"]["module"] == "app.main:app"
    assert conf["simulator"]["default_requests"] == 30
    # Optional loop-safety keys default to empty (present so --get never errors).
    assert conf["app"]["evaluator"] == ""
    assert conf["protected"]["paths"] == []


def test_unknown_section_survives(tmp_path):
    # The original loader iterated over DEFAULTS and silently dropped any
    # section it didn't know about. [traffic] must now come through.
    cfg = _write_config(tmp_path, '[traffic]\nreplay_file = "replay.jsonl"\n')
    conf = flywheel_config.load_config(cfg)
    assert "traffic" in conf
    # replay_file is a path key, so it comes back resolved against tmp_path.
    assert conf["traffic"]["replay_file"] == str((tmp_path / "replay.jsonl").resolve())


def test_path_keys_resolve_against_config_dir(tmp_path):
    cfg = _write_config(
        tmp_path,
        '[app]\nusage_log = "logs/u.jsonl"\n[simulator]\nedge_cases = "ec.json"\n',
    )
    conf = flywheel_config.load_config(cfg)
    assert conf["app"]["usage_log"] == str((tmp_path / "logs/u.jsonl").resolve())
    assert conf["simulator"]["edge_cases"] == str((tmp_path / "ec.json").resolve())


def test_non_path_keys_are_not_rewritten(tmp_path):
    # Resolving module/base_url as paths would corrupt them. Guard against it.
    cfg = _write_config(
        tmp_path,
        '[app]\nmodule = "pkg.api:app"\nbase_url = "http://localhost:9000"\n',
    )
    conf = flywheel_config.load_config(cfg)
    assert conf["app"]["module"] == "pkg.api:app"
    assert conf["app"]["base_url"] == "http://localhost:9000"


def test_empty_path_key_stays_empty(tmp_path):
    # An empty replay_file must not resolve to the config directory itself.
    cfg = _write_config(tmp_path, '[traffic]\nreplay_file = ""\n')
    conf = flywheel_config.load_config(cfg)
    assert conf["traffic"]["replay_file"] == ""


def test_env_var_selects_config(tmp_path, monkeypatch):
    cfg = _write_config(tmp_path, '[app]\nmodule = "from.env:app"\n')
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    conf = flywheel_config.load_config()
    assert conf["app"]["module"] == "from.env:app"


def test_explicit_path_beats_env(tmp_path, monkeypatch):
    env_cfg = _write_config(tmp_path, '[app]\nmodule = "from.env:app"\n')
    arg_cfg = tmp_path / "other.toml"
    arg_cfg.write_text('[app]\nmodule = "from.arg:app"\n')
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(env_cfg))
    conf = flywheel_config.load_config(arg_cfg)
    assert conf["app"]["module"] == "from.arg:app"


def test_two_configs_get_distinct_usage_logs(tmp_path):
    # The bug this whole change exists to fix: two apps must not share a log.
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    (a / "flywheel.toml").write_text('[app]\nusage_log = "usage.jsonl"\n')
    (b / "flywheel.toml").write_text('[app]\nusage_log = "usage.jsonl"\n')
    log_a = flywheel_config.load_config(a / "flywheel.toml")["app"]["usage_log"]
    log_b = flywheel_config.load_config(b / "flywheel.toml")["app"]["usage_log"]
    assert log_a != log_b


def test_load_edge_cases_reads_resolved_path(tmp_path):
    cfg = _write_config(tmp_path, '[simulator]\nedge_cases = "ec.json"\n')
    (tmp_path / "ec.json").write_text(json.dumps({"_doc": "ignored", "add": [{"a": 1, "b": 2}]}))
    conf = flywheel_config.load_config(cfg)
    ec = flywheel_config.load_edge_cases(conf)
    assert ec == {"add": [{"a": 1, "b": 2}]}


def test_load_edge_cases_absent_file_is_empty(tmp_path):
    cfg = _write_config(tmp_path, '[simulator]\nedge_cases = "missing.json"\n')
    conf = flywheel_config.load_config(cfg)
    assert flywheel_config.load_edge_cases(conf) == {}


def test_analyzer_defaults_empty_and_is_not_path_resolved(tmp_path):
    # app.analyzer is a command, not a path: it must survive verbatim, not be
    # rewritten relative to the config dir (that would corrupt the command).
    cfg = _write_config(tmp_path, '[app]\nanalyzer = "python engagements/x/analyze.py --source s"\n')
    conf = flywheel_config.load_config(cfg)
    assert conf["app"]["analyzer"] == "python engagements/x/analyze.py --source s"
    # A config that omits it gets the empty default (→ generic analyzer).
    d = tmp_path / "d"
    d.mkdir()
    assert flywheel_config.load_config(_write_config(d, "[app]\n"))["app"]["analyzer"] == ""


def test_engagement_config_wires_its_own_analyzer():
    from pathlib import Path

    eng = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "flywheel.toml"
    analyzer = flywheel_config.load_config(eng)["app"]["analyzer"]
    assert analyzer.endswith("analyze_integration.py --source forbes"), analyzer
