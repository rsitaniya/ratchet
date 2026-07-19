"""Tests for the protected-path enforcement the orchestrator runs before apply."""
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
