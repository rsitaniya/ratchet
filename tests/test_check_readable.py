"""The implementer's read boundary, tested the way it is attacked.

A read guard that only rejects a direct `Read` of a gold file is theatre: the
interesting cases are reaching held-out material through a parent directory, and
what happens when no config resolves.
"""
import io
import json

import check_readable
import pytest
from check_readable import blocked_hits, main, requested_paths

GLOBS = ["**/fixtures/**", "**/gold_*.json", "**/runs/**"]


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A miniature engagement: some readable source, some held-out material."""
    (tmp_path / "engagements/demo/fixtures/sources").mkdir(parents=True)
    (tmp_path / "engagements/demo/fixtures/gold_mapping.json").write_text('{"forbes": {}}')
    (tmp_path / "engagements/demo/fixtures/sources/forbes.jsonl").write_text('{"a": 1}\n')
    (tmp_path / "engagements/demo/adapters").mkdir(parents=True)
    (tmp_path / "engagements/demo/adapters/forbes.toml").write_text('source = "forbes"\n')
    (tmp_path / "engagements/demo/app.py").write_text("app = 1\n")
    (tmp_path / "engagements/demo/runs").mkdir(parents=True)
    (tmp_path / "engagements/demo/runs/01_cycle1.adapter.toml").write_text("converged = true\n")

    cfg = tmp_path / "flywheel.toml"
    cfg.write_text(
        '[app]\nmodule = "demo:app"\n\n[protected]\npaths = []\nunreadable = '
        + json.dumps(GLOBS)
        + "\n"
    )
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(tool_name, tool_input):
    return main(io.StringIO(json.dumps({"tool_name": tool_name, "tool_input": tool_input})))


def test_requested_paths_reads_every_tool_shape():
    assert requested_paths({"file_path": "a.py"}) == ["a.py"]
    assert requested_paths({"path": "src"}) == ["src"]
    assert requested_paths({"pattern": "def foo"}) == []


def test_reading_gold_directly_is_denied(repo):
    assert run("Read", {"file_path": "engagements/demo/fixtures/gold_mapping.json"}) == 2


def test_reading_the_source_records_gold_came_from_is_denied(repo):
    assert run("Read", {"file_path": "engagements/demo/fixtures/sources/forbes.jsonl"}) == 2


def test_reading_a_prior_converged_receipt_is_denied(repo):
    assert run("Read", {"file_path": "engagements/demo/runs/01_cycle1.adapter.toml"}) == 2


def test_reading_the_adapter_it_must_edit_is_allowed(repo):
    assert run("Read", {"file_path": "engagements/demo/adapters/forbes.toml"}) == 0


def test_reading_the_app_source_is_allowed(repo):
    assert run("Read", {"file_path": "engagements/demo/app.py"}) == 0


def test_grepping_a_parent_directory_cannot_reach_gold(repo):
    """The bypass that makes a name-matching guard useless: gold sits under a
    directory whose own name matches no protected glob."""
    assert run("Grep", {"path": "engagements/demo", "pattern": "forbes"}) == 2


def test_grepping_the_repo_root_is_denied_too(repo):
    assert run("Grep", {"path": ".", "pattern": "forbes"}) == 2


def test_grepping_a_clean_directory_is_allowed(repo):
    assert run("Grep", {"path": "engagements/demo/adapters", "pattern": "forbes"}) == 0


def test_absolute_path_to_gold_is_denied(repo):
    target = repo / "engagements/demo/fixtures/gold_mapping.json"
    assert run("Read", {"file_path": str(target)}) == 2


def test_traversal_out_and_back_into_gold_is_denied(repo):
    assert run("Read", {"file_path": "engagements/demo/adapters/../fixtures/gold_mapping.json"}) == 2


def test_nonexistent_protected_path_is_still_denied(repo):
    """A guard decision must not depend on whether the file happens to exist."""
    assert run("Read", {"file_path": "engagements/demo/fixtures/not_yet.jsonl"}) == 2


def test_no_config_fails_closed(repo, monkeypatch):
    monkeypatch.delenv("FLYWHEEL_CONFIG")
    (repo / "flywheel.toml").unlink()
    assert run("Read", {"file_path": "engagements/demo/adapters/forbes.toml"}) == 2


def test_missing_configured_file_fails_closed(repo, monkeypatch):
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(repo / "nope.toml"))
    assert run("Read", {"file_path": "engagements/demo/adapters/forbes.toml"}) == 2


def test_empty_unreadable_list_allows_everything(tmp_path, monkeypatch):
    """An explicit empty list is a choice; a missing config is not (above)."""
    cfg = tmp_path / "flywheel.toml"
    cfg.write_text('[app]\nmodule = "demo:app"\n\n[protected]\npaths = []\nunreadable = []\n')
    (tmp_path / "gold_mapping.json").write_text("{}")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(tmp_path)
    assert run("Read", {"file_path": "gold_mapping.json"}) == 0


def test_malformed_hook_payload_fails_closed(repo):
    assert main(io.StringIO("not json")) == 2


def test_payload_without_tool_input_fails_closed(repo):
    assert main(io.StringIO(json.dumps({"tool_name": "Read", "tool_input": "oops"}))) == 2


def test_payload_with_no_path_is_allowed(repo):
    """A Grep with only a pattern names nothing to judge; the tool grant bounds it."""
    assert run("Grep", {"pattern": "def foo"}) == 0


def test_blocked_hits_reports_every_offending_file(repo):
    hits = blocked_hits(["engagements/demo/fixtures"], GLOBS, repo.resolve())
    assert "engagements/demo/fixtures/gold_mapping.json" in hits
    assert "engagements/demo/fixtures/sources/forbes.jsonl" in hits


def test_walk_skips_noise_directories(repo):
    """A .venv full of files named gold_*.json would make every grep unusable."""
    (repo / "engagements/demo/.venv").mkdir()
    (repo / "engagements/demo/.venv/gold_x.json").write_text("{}")
    assert check_readable.SKIP_DIRS & {".venv"}
    hits = blocked_hits(["engagements/demo/adapters"], GLOBS, repo.resolve())
    assert hits == []


def test_the_real_engagement_config_holds_out_gold(monkeypatch):
    """Not a synthetic config: the boundary the shipped engagement actually declares."""
    monkeypatch.setenv("FLYWHEEL_CONFIG", "engagements/madi_onboarding/flywheel.toml")
    assert run("Read", {"file_path": "engagements/madi_onboarding/fixtures/gold_records.jsonl"}) == 2
    assert run("Read", {"file_path": "engagements/madi_onboarding/adapters/forbes.toml"}) == 0
