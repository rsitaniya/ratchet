"""Tests for the single entry point that guards, checks, and applies a patch."""
import subprocess

import apply_patch as AP


def _init_repo(repo, files: dict[str, str]):
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    for name, content in files.items():
        (repo / name).write_text(content)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=repo, check=True)


def _edit_diff(path: str, old: str, new: str) -> str:
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-{old}\n+{new}\n"


def test_guard_rejection_blocks_apply(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"evaluate.py": "old\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text('[protected]\npaths = ["**/evaluate.py"]\n')
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    patch = repo / "p.patch"
    patch.write_text(_edit_diff("evaluate.py", "old", "new"))
    assert AP.apply_patch(patch) == 2
    assert (repo / "evaluate.py").read_text() == "old\n"  # never touched


def test_clean_patch_applies(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "old\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text('[protected]\npaths = ["**/evaluate.py"]\n')
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    patch = repo / "p.patch"
    patch.write_text(_edit_diff("adapter.toml", "old", "new"))
    assert AP.apply_patch(patch) == 0
    assert (repo / "adapter.toml").read_text() == "new\n"


def test_apply_check_failure_surfaces_git_error(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "different content entirely\n"})
    cfg = repo / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(repo)

    # Patch context doesn't match the file on disk — git apply --check must fail.
    patch = repo / "p.patch"
    patch.write_text(_edit_diff("adapter.toml", "old", "new"))
    assert AP.apply_patch(patch) != 0
    assert (repo / "adapter.toml").read_text() == "different content entirely\n"


def test_no_config_blocks_apply(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    _init_repo(repo, {"adapter.toml": "old\n"})
    monkeypatch.delenv("FLYWHEEL_CONFIG", raising=False)
    monkeypatch.chdir(repo)
    monkeypatch.setattr("check_protected_paths.config_path", lambda: repo / "nope.toml")

    patch = repo / "p.patch"
    patch.write_text(_edit_diff("adapter.toml", "old", "new"))
    assert AP.apply_patch(patch) == 2
    assert (repo / "adapter.toml").read_text() == "old\n"
