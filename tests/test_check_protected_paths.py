"""Tests for the protected-path enforcement the orchestrator runs before apply."""
import subprocess
import tomllib
from pathlib import Path

import check_protected_paths as C

ENGAGEMENT_GLOBS = ["**/evaluate.py", "**/adapters.py", "**/fixtures/**", "**/gold_*.json", "**/*_gold.json"]

BASE = "engagements/madi_onboarding"
ADAPTER = f"{BASE}/adapters/forbes.toml"
EVALUATOR = f"{BASE}/evaluate.py"
GOLD = f"{BASE}/fixtures/gold_records.jsonl"


def _diff(path: str) -> str:
    """Minimal in-place-edit unified diff touching `path`."""
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -1 +1 @@\n-old\n+new\n"


def _rename_diff(old: str, new: str) -> str:
    """A pure git rename diff — note it has NO +++/--- content lines."""
    return f"diff --git a/{old} b/{new}\nsimilarity index 100%\nrename from {old}\nrename to {new}\n"


def _delete_diff(path: str) -> str:
    """A git deletion diff — the target side is /dev/null."""
    return f"diff --git a/{path} b/{path}\ndeleted file mode 100644\n--- a/{path}\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n"


def _write_patch(tmp_path, diff_text: str) -> Path:
    patch = tmp_path / "p.patch"
    patch.write_text(diff_text)
    return patch


def _real_git_diff(tmp_path, setup) -> str:
    """Run `setup(repo_dir)` in a fresh repo and return its staged diff text."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    setup(repo)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    return subprocess.run(["git", "diff", "--cached"], cwd=repo, capture_output=True, text=True).stdout


# --- Path detection via `git apply --numstat -z` ---


def test_parse_numstat_z_ordinary_records():
    assert C._parse_numstat_z(b"1\t0\tevaluate.py\0") == ["evaluate.py"]
    assert C._parse_numstat_z(b"1\t0\ta.txt\x002\t1\tb.txt\0") == ["a.txt", "b.txt"]


def test_adapter_edit_is_allowed(tmp_path):
    patch = _write_patch(tmp_path, _diff(ADAPTER))
    assert C.protected_hits(C.paths_touched(patch), ENGAGEMENT_GLOBS) == []


def test_editing_the_evaluator_is_blocked(tmp_path):
    patch = _write_patch(tmp_path, _diff(EVALUATOR))
    hits = C.protected_hits(C.paths_touched(patch), ENGAGEMENT_GLOBS)
    assert hits and hits[0][0].endswith("evaluate.py")


def test_editing_gold_is_blocked(tmp_path):
    patch = _write_patch(tmp_path, _diff(GOLD))
    assert C.protected_hits(C.paths_touched(patch), ENGAGEMENT_GLOBS)


def test_deleting_gold_is_blocked(tmp_path):
    patch = _write_patch(tmp_path, _delete_diff(GOLD))
    assert C.protected_hits(C.paths_touched(patch), ENGAGEMENT_GLOBS)


def test_mapping_engine_is_protected():
    assert C.protected_hits([f"{BASE}/adapters.py"], ENGAGEMENT_GLOBS)


def test_root_level_paths_still_match():
    # `**/evaluate.py` must catch a repo-root evaluate.py, however the diff is prefixed.
    assert C.protected_hits(["evaluate.py"], ENGAGEMENT_GLOBS)


def test_normalizers_and_adapter_data_stay_writable():
    # The loop must still be able to add normalizers and adapter mappings.
    assert C.protected_hits([f"{BASE}/normalizers.py"], ENGAGEMENT_GLOBS) == []
    assert C.protected_hits([ADAPTER], ENGAGEMENT_GLOBS) == []


def test_no_globs_means_nothing_protected(tmp_path):
    # An app that declares no protected paths → nothing is blocked.
    patch = _write_patch(tmp_path, _diff(EVALUATOR))
    assert C.protected_hits(C.paths_touched(patch), []) == []


def test_engagement_config_protects_loop_machinery():
    # The engagement must forbid editing its own config and orchestration, or the
    # loop could disable the evaluator or weaken the guard itself.
    cfg = tomllib.loads((Path(__file__).resolve().parent.parent / BASE / "flywheel.toml").read_text())
    globs = cfg["protected"]["paths"]
    assert C.protected_hits([f"{BASE}/flywheel.toml"], globs)          # the config declaring the evaluator
    assert C.protected_hits(["scripts/check_protected_paths.py"], globs)  # the guard
    assert C.protected_hits([".claude/skills/dev-loop/SKILL.md"], globs)  # the orchestrator
    assert C.protected_hits([EVALUATOR], globs)
    # matching.py is protected specifically because it runs similarity.py's
    # scoring functions — the dependency must be protected too, or rigging
    # e.g. jaro_winkler() inflates entity-matching F1 with no gold access at all.
    assert C.protected_hits([f"{BASE}/similarity.py"], globs)
    # This repo's actual gold files are .jsonl, not .json — the gold-specific
    # globs must catch the real extension on their own, independent of the
    # fixtures/** directory glob (a path outside fixtures/, e.g. reached
    # through a symlink, must still be caught by the gold-name glob itself).
    assert C.protected_hits(["gold_pairs.jsonl"], globs)
    # ...but the loop can still grow adapter data and normalizers.
    assert C.protected_hits([ADAPTER], globs) == []
    assert C.protected_hits([f"{BASE}/normalizers.py"], globs) == []


def test_unparseable_patch_fails_closed(tmp_path):
    patch = _write_patch(tmp_path, "this is not a diff at all\n")
    try:
        C.paths_touched(patch)
        raise AssertionError("expected PatchParseError")
    except C.PatchParseError:
        pass


# --- Git-generated paths, including one Git chooses to quote ---


def test_paths_touched_handles_a_real_git_patch(tmp_path):
    diff = _real_git_diff(tmp_path, lambda repo: (repo / "evaluate.py").write_text("x\n"))
    patch = _write_patch(tmp_path, diff)
    assert C.paths_touched(patch) == ["evaluate.py"]


def test_paths_touched_handles_git_quoted_non_ascii_name(tmp_path):
    # Git wraps a path with special bytes in quotes and escapes it (core.quotePath).
    # `git apply --numstat -z` reports the raw unquoted bytes directly — no
    # hand-rolled decoder needed on this side, which is the whole point of
    # relying on numstat instead of parsing diff headers as text.
    name = "évalué.py"
    diff = _real_git_diff(tmp_path, lambda repo: (repo / name).write_text("x\n"))
    assert '"' in diff.splitlines()[0]  # confirm git actually quoted it
    patch = _write_patch(tmp_path, diff)
    assert C.paths_touched(patch) == [name]


# --- Rename / copy: rejected outright, not path-checked ---


def test_has_rename_or_copy_detects_rename():
    assert C.has_rename_or_copy(_rename_diff(EVALUATOR, f"{BASE}/eval_moved.py"))


def test_has_rename_or_copy_false_for_ordinary_edit():
    assert not C.has_rename_or_copy(_diff(ADAPTER))
    assert not C.has_rename_or_copy(_delete_diff(GOLD))


def test_rename_of_evaluator_rejected_end_to_end(tmp_path, monkeypatch):
    # A rename is rejected before path-checking even runs — numstat reports
    # only the rename's destination, never its source, so accepting renames
    # at all would need a second detector for exactly the path this guard
    # exists to catch leaving through.
    monkeypatch.setattr(C, "_resolve_config_or_reject", lambda: Path("dummy"))
    monkeypatch.setattr(C, "get_value", lambda key: ENGAGEMENT_GLOBS if key == "protected.paths" else None)
    patch = _write_patch(tmp_path, _rename_diff(EVALUATOR, f"{BASE}/eval_moved.py"))
    assert C.main([str(patch)]) == 2


def test_real_git_rename_rejected_end_to_end(tmp_path, monkeypatch):
    def setup(repo):
        (repo / "evaluate.py").write_text("gold_scoring = 1\n")
        subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
        subprocess.run(
            ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
            cwd=repo, check=True,
        )
        subprocess.run(["git", "mv", "evaluate.py", "eval_moved.py"], cwd=repo, check=True)

    diff = _real_git_diff(tmp_path, setup)
    monkeypatch.setattr(C, "_resolve_config_or_reject", lambda: Path("dummy"))
    monkeypatch.setattr(C, "get_value", lambda key: ENGAGEMENT_GLOBS if key == "protected.paths" else None)
    patch = _write_patch(tmp_path, diff)
    assert C.main([str(patch)]) == 2


def test_copy_rejected_end_to_end(tmp_path, monkeypatch):
    diff = (
        f"diff --git a/{ADAPTER} b/{BASE}/adapters/forbes2.toml\n"
        "similarity index 90%\n"
        f"copy from {ADAPTER}\n"
        f"copy to {BASE}/adapters/forbes2.toml\n"
    )
    monkeypatch.setattr(C, "_resolve_config_or_reject", lambda: Path("dummy"))
    monkeypatch.setattr(C, "get_value", lambda key: ENGAGEMENT_GLOBS if key == "protected.paths" else None)
    patch = _write_patch(tmp_path, diff)
    assert C.main([str(patch)]) == 2


# --- Symlinks: rejected outright ---


def test_symlink_creation_is_detected():
    # Real `git diff` output for `ln -s fixtures shim; git add shim`.
    diff = (
        "diff --git a/shim b/shim\n"
        "new file mode 120000\n"
        "index 0000000..d488960\n"
        "--- /dev/null\n"
        "+++ b/shim\n"
        "@@ -0,0 +1 @@\n"
        "+fixtures\n"
        "\\ No newline at end of file\n"
    )
    assert C.has_symlink_mode_change(diff)


def test_symlink_repoint_is_detected():
    # Real `git diff` output for repointing an *existing* symlink — mode is
    # unchanged (still 120000), so it only shows up on the index line.
    diff = (
        "diff --git a/shim b/shim\n"
        "index 2e65efe..d488960 120000\n"
        "--- a/shim\n"
        "+++ b/shim\n"
        "@@ -1 +1 @@\n"
        "-a\n"
        "\\ No newline at end of file\n"
        "+fixtures\n"
        "\\ No newline at end of file\n"
    )
    assert C.has_symlink_mode_change(diff)


def test_ordinary_file_edit_is_not_flagged_as_symlink():
    assert not C.has_symlink_mode_change(_diff(ADAPTER))
    assert not C.has_symlink_mode_change(_delete_diff(GOLD))


def test_symlink_bypass_end_to_end_via_main(tmp_path, monkeypatch):
    # The review's exploit: a symlink into a protected directory, then a write
    # through it to a path no glob matches, previously passed with exit 0.
    monkeypatch.setattr(C, "_resolve_config_or_reject", lambda: Path("dummy"))
    monkeypatch.setattr(C, "get_value", lambda key: ENGAGEMENT_GLOBS if key == "protected.paths" else None)
    patch = _write_patch(
        tmp_path,
        "diff --git a/shim b/shim\n"
        "new file mode 120000\n"
        "index 0000000..d488960\n"
        "--- /dev/null\n"
        "+++ b/shim\n"
        "@@ -0,0 +1 @@\n"
        f"+{BASE}/fixtures\n"
        "\\ No newline at end of file\n",
    )
    assert C.main([str(patch)]) == 2


# --- Config resolution: the guard must not run with no config ---


def test_rejects_when_no_config_resolves(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_resolve_config_or_reject", lambda: None)
    patch = _write_patch(tmp_path, _diff(EVALUATOR))
    assert C.main([str(patch)]) == 2


def test_missing_flywheel_config_env_is_rejected_not_defaulted(tmp_path, monkeypatch):
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(tmp_path / "does-not-exist.toml"))
    assert C._resolve_config_or_reject() is None


def test_no_config_at_all_is_rejected(tmp_path, monkeypatch):
    monkeypatch.delenv("FLYWHEEL_CONFIG", raising=False)
    monkeypatch.setattr(C, "config_path", lambda: tmp_path / "nope.toml")
    assert C._resolve_config_or_reject() is None


def test_existing_config_with_empty_protected_list_passes(tmp_path, monkeypatch):
    cfg = tmp_path / "flywheel.toml"
    cfg.write_text("[protected]\npaths = []\n")
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    patch = _write_patch(tmp_path, _diff(EVALUATOR))
    assert C.main([str(patch)]) == 0


def test_end_to_end_rejects_evaluator_edit_with_real_engagement_config(tmp_path, monkeypatch):
    eng_cfg = Path(__file__).resolve().parent.parent / BASE / "flywheel.toml"
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(eng_cfg))
    patch = _write_patch(tmp_path, _diff(EVALUATOR))
    assert C.main([str(patch)]) == 2
