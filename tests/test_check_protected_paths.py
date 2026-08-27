"""Tests for the protected-path enforcement the orchestrator runs before apply."""
import json
import tomllib
from pathlib import Path

import check_protected_paths as C

ENGAGEMENT_GLOBS = ["**/evaluate.py", "**/adapters.py", "**/fixtures/**", "**/gold_*.json", "**/*_gold.json"]

BASE = "engagements/madi_onboarding"
ADAPTER = f"{BASE}/adapters/forbes.toml"
EVALUATOR = f"{BASE}/evaluate.py"
GOLD = f"{BASE}/fixtures/gold_records.jsonl"


def _edits(*files: str) -> list[dict]:
    """Minimal edit list touching each of `files` — content doesn't matter here."""
    return [{"file": f, "old_string": "old", "new_string": "new"} for f in files]


def _write_edits(tmp_path, edits: list[dict]) -> Path:
    editsfile = tmp_path / "edits.json"
    editsfile.write_text(json.dumps(edits))
    return editsfile


# --- Path detection from the edit list itself ---


def test_touched_paths_dedupes_and_sorts():
    edits = _edits(f"{BASE}/b.toml", f"{BASE}/a.toml", f"{BASE}/a.toml")
    assert C.touched_paths(edits, Path.cwd()) == sorted({f"{BASE}/b.toml", f"{BASE}/a.toml"})


def test_adapter_edit_is_allowed():
    assert C.protected_hits([ADAPTER], ENGAGEMENT_GLOBS) == []


def test_editing_the_evaluator_is_blocked():
    hits = C.protected_hits([EVALUATOR], ENGAGEMENT_GLOBS)
    assert hits and hits[0][0].endswith("evaluate.py")


def test_editing_gold_is_blocked():
    assert C.protected_hits([GOLD], ENGAGEMENT_GLOBS)


def test_mapping_engine_is_protected():
    assert C.protected_hits([f"{BASE}/adapters.py"], ENGAGEMENT_GLOBS)


def test_root_level_paths_still_match():
    # `**/evaluate.py` must catch a repo-root evaluate.py, however the edit's path is written.
    assert C.protected_hits(["evaluate.py"], ENGAGEMENT_GLOBS)


def test_normalizers_and_adapter_data_stay_writable():
    # The loop must still be able to add normalizers and adapter mappings.
    assert C.protected_hits([f"{BASE}/normalizers.py"], ENGAGEMENT_GLOBS) == []
    assert C.protected_hits([ADAPTER], ENGAGEMENT_GLOBS) == []


def test_no_globs_means_nothing_protected(tmp_path, monkeypatch):
    # An app that declares no protected paths → nothing is blocked.
    monkeypatch.setattr(C, "_resolve_config_or_reject", lambda: Path("dummy"))
    monkeypatch.setattr(C, "get_value", lambda key: [] if key == "protected.paths" else None)
    editsfile = _write_edits(tmp_path, _edits(EVALUATOR))
    assert C.main([str(editsfile)]) == 0


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
    # fixtures/** directory glob.
    assert C.protected_hits(["gold_pairs.jsonl"], globs)
    # ...but the loop can still grow adapter data and normalizers.
    assert C.protected_hits([ADAPTER], globs) == []
    assert C.protected_hits([f"{BASE}/normalizers.py"], globs) == []


# --- Rename / copy / symlink: not detected, because they cannot be expressed ---
#
# A diff-based patch could rename, copy, or symlink a file; a JSON edit list of
# {file, old_string, new_string} has no operation that does any of those things
# — an edit's `file` names exactly one path to read-and-replace or create, full
# stop. There is nothing left to write a detector for. The end-to-end tests
# below confirm the *paths* that mattered in the old rename/copy/symlink exploits
# — the protected evaluator, an escape via a fabricated destination path — are
# still correctly rejected via the ordinary path-matching path.


def test_evaluator_targeted_via_any_path_shape_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_resolve_config_or_reject", lambda: Path("dummy"))
    monkeypatch.setattr(C, "get_value", lambda key: ENGAGEMENT_GLOBS if key == "protected.paths" else None)
    editsfile = _write_edits(tmp_path, [{"file": EVALUATOR, "old_string": "", "new_string": "x"}])
    assert C.main([str(editsfile)]) == 2


# --- Config resolution: the guard must not run with no config ---


def test_rejects_when_no_config_resolves(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "_resolve_config_or_reject", lambda: None)
    editsfile = _write_edits(tmp_path, _edits(EVALUATOR))
    assert C.main([str(editsfile)]) == 2


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
    editsfile = _write_edits(tmp_path, _edits(EVALUATOR))
    assert C.main([str(editsfile)]) == 0


def test_end_to_end_rejects_evaluator_edit_with_real_engagement_config(tmp_path, monkeypatch):
    eng_cfg = Path(__file__).resolve().parent.parent / BASE / "flywheel.toml"
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(eng_cfg))
    editsfile = _write_edits(tmp_path, _edits(EVALUATOR))
    assert C.main([str(editsfile)]) == 2


def test_malformed_edits_json_fails_closed(tmp_path, monkeypatch):
    eng_cfg = Path(__file__).resolve().parent.parent / BASE / "flywheel.toml"
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(eng_cfg))
    editsfile = tmp_path / "edits.json"
    editsfile.write_text("not json")
    assert C.main([str(editsfile)]) == 2


def test_edits_file_must_be_a_json_list(tmp_path, monkeypatch):
    eng_cfg = Path(__file__).resolve().parent.parent / BASE / "flywheel.toml"
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(eng_cfg))
    editsfile = tmp_path / "edits.json"
    editsfile.write_text(json.dumps({"file": EVALUATOR}))  # a dict, not a list
    assert C.main([str(editsfile)]) == 2
