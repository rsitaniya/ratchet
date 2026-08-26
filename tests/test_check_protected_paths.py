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


def test_changed_paths_parsing():
    assert C.changed_paths(_diff(ADAPTER)) == [ADAPTER]


def test_adapter_edit_is_allowed():
    assert C.protected_hits(C.changed_paths(_diff(ADAPTER)), ENGAGEMENT_GLOBS) == []


def test_editing_the_evaluator_is_blocked():
    hits = C.protected_hits(C.changed_paths(_diff(EVALUATOR)), ENGAGEMENT_GLOBS)
    assert hits and hits[0][0].endswith("evaluate.py")


def test_editing_gold_is_blocked():
    assert C.protected_hits(C.changed_paths(_diff(GOLD)), ENGAGEMENT_GLOBS)


def test_renaming_the_evaluator_away_is_blocked():
    # A rename diff carries no +++ line; the old path must still be caught.
    hits = C.protected_hits(C.changed_paths(_rename_diff(EVALUATOR, f"{BASE}/eval_moved.py")), ENGAGEMENT_GLOBS)
    assert any(p == EVALUATOR for p, _ in hits), "rename of a protected file must be blocked"


def test_deleting_gold_is_blocked():
    # A deletion diff points the target at /dev/null; the source path must be caught.
    assert C.protected_hits(C.changed_paths(_delete_diff(GOLD)), ENGAGEMENT_GLOBS)


def test_mapping_engine_is_protected():
    assert C.protected_hits([f"{BASE}/adapters.py"], ENGAGEMENT_GLOBS)


def test_root_level_and_unprefixed_paths_still_match():
    # `**/evaluate.py` must catch a repo-root evaluate.py and a --no-prefix diff path.
    assert C.protected_hits(["evaluate.py"], ENGAGEMENT_GLOBS)
    assert C.changed_paths("+++ evaluate.py\n") == ["evaluate.py"]
    assert C.protected_hits(C.changed_paths("+++ evaluate.py\n"), ENGAGEMENT_GLOBS)


def test_normalizers_and_adapter_data_stay_writable():
    # The loop must still be able to add normalizers and adapter mappings.
    assert C.protected_hits([f"{BASE}/normalizers.py"], ENGAGEMENT_GLOBS) == []
    assert C.protected_hits([ADAPTER], ENGAGEMENT_GLOBS) == []


def test_no_globs_means_nothing_protected():
    # The calculator declares no protected paths → nothing is blocked.
    assert C.protected_hits(C.changed_paths(_diff(EVALUATOR)), []) == []


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


# --- Git-native path detection (the real security boundary) ---


def test_parse_numstat_z_normal_and_rename():
    # Layout confirmed empirically: normal = "a\tr\tpath\0"; rename = "a\tr\t\0old\0new\0".
    assert C._parse_numstat_z(b"1\t0\tevaluate.py\0") == ["evaluate.py"]
    assert C._parse_numstat_z(b"0\t0\t\0a.txt\0b.txt\0") == ["a.txt", "b.txt"]


def test_quoted_path_bypass_is_caught(tmp_path):
    # The review's exploit: an octal-escaped path defeats a naive text parser,
    # but `git apply` unquotes it to the real file. paths_touched must see it.
    patch = tmp_path / "evil.patch"
    patch.write_text(
        'diff --git "a/\\145valuate.py" "b/\\145valuate.py"\n'
        '--- "a/\\145valuate.py"\n'
        '+++ "b/\\145valuate.py"\n'
        "@@ -0,0 +1 @@\n+x\n"
    )
    # git-native detection resolves the real target from the escaped path.
    assert C.paths_touched(patch) == ["evaluate.py"]
    assert C.protected_hits(sorted(C.all_touched_paths(patch)), ENGAGEMENT_GLOBS)


def test_quoted_evaluator_edit_rejected_end_to_end(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "get_value", lambda key: ENGAGEMENT_GLOBS if key == "protected.paths" else None)
    patch = tmp_path / "evil.patch"
    patch.write_text(
        'diff --git "a/\\145valuate.py" "b/\\145valuate.py"\n'
        '--- "a/\\145valuate.py"\n'
        '+++ "b/\\145valuate.py"\n'
        "@@ -0,0 +1 @@\n+x\n"
    )
    assert C.main([str(patch)]) == 2


def test_unparseable_patch_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "get_value", lambda key: ENGAGEMENT_GLOBS if key == "protected.paths" else None)
    patch = tmp_path / "garbage.patch"
    patch.write_text("this is not a diff at all\n")
    assert C.main([str(patch)]) == 2  # cannot prove safe → reject


def test_union_catches_rename_of_evaluator(tmp_path, monkeypatch):
    # numstat reports only the rename destination; the union must still catch the
    # protected source. This is a real git-generated rename patch.
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "evaluate.py").write_text("gold_scoring = 1\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"], cwd=repo, check=True)
    subprocess.run(["git", "mv", "evaluate.py", "eval_moved.py"], cwd=repo, check=True)
    diff = subprocess.run(["git", "diff", "--cached"], cwd=repo, capture_output=True, text=True).stdout
    patch = repo / "r.patch"
    patch.write_text(diff)
    subprocess.run(["git", "reset", "-q"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    assert "evaluate.py" in C.all_touched_paths(patch)
    assert C.protected_hits(sorted(C.all_touched_paths(patch)), ENGAGEMENT_GLOBS)


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
    monkeypatch.setattr(C, "get_value", lambda key: ENGAGEMENT_GLOBS if key == "protected.paths" else None)
    patch = tmp_path / "symlink.patch"
    patch.write_text(
        "diff --git a/shim b/shim\n"
        "new file mode 120000\n"
        "index 0000000..d488960\n"
        "--- /dev/null\n"
        "+++ b/shim\n"
        "@@ -0,0 +1 @@\n"
        f"+{BASE}/fixtures\n"
        "\\ No newline at end of file\n"
    )
    assert C.main([str(patch)]) == 2


def test_git_unquote_matches_real_git(tmp_path):
    # Verify _git_unquote reproduces exactly what git wrote, for a non-ASCII path
    # git chose to quote (following the rule: check against the tool, not memory).
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    name = "évalué.py"
    (repo / name).write_text("x\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    header = subprocess.run(
        ["git", "diff", "--cached"], cwd=repo, capture_output=True, text=True
    ).stdout.splitlines()[0]
    # header like: diff --git "a/\303\251valu\303\251.py" "b/\303\251valu\303\251.py"
    assert '"' in header  # git did quote it
    token = header[len("diff --git "):].split(" ", 1)[0]
    assert C._git_unquote(token) == f"a/{name}"
