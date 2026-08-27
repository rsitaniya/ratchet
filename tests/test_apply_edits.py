"""Tests for the single entry point that guards, validates, and applies edits."""
import json
import subprocess

import apply_edits as AE


def _init_repo(repo, files: dict[str, str]):
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    for name, content in files.items():
        (repo / name).write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=repo, check=True)


def _write_edits(repo, edits: list[dict]):
    editsfile = repo / "edits.json"
    editsfile.write_text(json.dumps(edits))
    return editsfile


def test_guard_rejection_blocks_apply(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"evaluate.py": "old\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text('[protected]\npaths = ["**/evaluate.py"]\n')
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(repo, [{"file": "evaluate.py", "old_string": "old\n", "new_string": "new\n"}])
    assert AE.main([str(editsfile)]) == 2
    assert (repo / "evaluate.py").read_text() == "old\n"  # never touched


def test_clean_edit_applies(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "old\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text('[protected]\npaths = ["**/evaluate.py"]\n')
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(repo, [{"file": "adapter.toml", "old_string": "old\n", "new_string": "new\n"}])
    assert AE.main([str(editsfile)]) == 0
    assert (repo / "adapter.toml").read_text() == "new\n"


def test_new_file_creation(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"README.md": "x\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(
        repo, [{"file": "tests/test_new.py", "old_string": "", "new_string": "def test_x(): pass\n"}]
    )
    assert AE.main([str(editsfile)]) == 0
    assert (repo / "tests" / "test_new.py").read_text() == "def test_x(): pass\n"


def test_old_string_not_found_rejects_without_writing(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "different content entirely\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(repo, [{"file": "adapter.toml", "old_string": "old\n", "new_string": "new\n"}])
    assert AE.main([str(editsfile)]) == 1
    assert (repo / "adapter.toml").read_text() == "different content entirely\n"


def test_old_string_not_unique_rejects(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "x\nx\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(repo, [{"file": "adapter.toml", "old_string": "x\n", "new_string": "y\n"}])
    assert AE.main([str(editsfile)]) == 1
    assert (repo / "adapter.toml").read_text() == "x\nx\n"


def test_create_on_existing_file_rejects(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "already here\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(repo, [{"file": "adapter.toml", "old_string": "", "new_string": "overwrite\n"}])
    assert AE.main([str(editsfile)]) == 1
    assert (repo / "adapter.toml").read_text() == "already here\n"


def test_one_bad_edit_rejects_the_whole_batch_atomically(tmp_path, monkeypatch):
    # Two edits in one submission: the first is valid, the second is not. Neither
    # should land — a submission is all-or-nothing, not partially applied.
    repo = tmp_path / "repo"
    _init_repo(repo, {"a.toml": "a-old\n", "b.toml": "b-old\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(repo, [
        {"file": "a.toml", "old_string": "a-old\n", "new_string": "a-new\n"},
        {"file": "b.toml", "old_string": "does-not-exist", "new_string": "b-new\n"},
    ])
    assert AE.main([str(editsfile)]) == 1
    assert (repo / "a.toml").read_text() == "a-old\n"  # not applied despite being valid on its own
    assert (repo / "b.toml").read_text() == "b-old\n"


def test_sequential_edits_to_the_same_file(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "line1\nline2\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(repo, [
        {"file": "adapter.toml", "old_string": "line1\n", "new_string": "line1-edited\n"},
        {"file": "adapter.toml", "old_string": "line2\n", "new_string": "line2-edited\n"},
    ])
    assert AE.main([str(editsfile)]) == 0
    assert (repo / "adapter.toml").read_text() == "line1-edited\nline2-edited\n"


def test_path_escaping_repo_root_rejected(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "old\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = _write_edits(repo, [{"file": "../outside.toml", "old_string": "", "new_string": "x\n"}])
    assert AE.main([str(editsfile)]) == 1
    assert not (tmp_path / "outside.toml").exists()


def test_no_config_blocks_apply(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "old\n"})
    monkeypatch.delenv("FLYWHEEL_CONFIG", raising=False)
    monkeypatch.chdir(repo)
    monkeypatch.setattr("check_protected_paths.config_path", lambda: repo / "nope.toml")

    editsfile = _write_edits(repo, [{"file": "adapter.toml", "old_string": "old\n", "new_string": "new\n"}])
    assert AE.main([str(editsfile)]) == 2
    assert (repo / "adapter.toml").read_text() == "old\n"


def test_malformed_edits_json_rejected(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "old\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    editsfile = repo / "edits.json"
    editsfile.write_text("not json")
    assert AE.main([str(editsfile)]) == 2
