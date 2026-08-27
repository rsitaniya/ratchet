"""Delivery telemetry: the numbers behind the economics claim.

These assert the derivations the loop must not get wrong — a resubmission is
counted, an unmeasured metric never becomes a 0.0 delta, and a skipped cycle
never moves the acceptance rate.
"""
import json

import cycle_log
import pytest
from cycle_log import durations, edit_stats, main, metric_deltas, summarize


@pytest.fixture
def cycle(tmp_path, monkeypatch):
    cfg = tmp_path / "flywheel.toml"
    cfg.write_text(
        '[app]\nmodule = "demo:app"\ncycle_log = "runs/delivery/cycles.jsonl"\n'
        "\n[protected]\npaths = []\nunreadable = []\n"
    )
    monkeypatch.setenv("FLYWHEEL_CONFIG", str(cfg))
    monkeypatch.chdir(tmp_path)
    return tmp_path


def records(path):
    return [json.loads(ln) for ln in path.read_text().splitlines() if ln.strip()]


def test_durations_are_deltas_between_stamps():
    marks = [
        {"phase": "simulate", "at": "2026-08-27T10:00:10+00:00", "t0": "2026-08-27T10:00:00+00:00"},
        {"phase": "analyze", "at": "2026-08-27T10:00:15+00:00", "t0": "2026-08-27T10:00:00+00:00"},
    ]
    assert durations(marks) == {"simulate": 10.0, "analyze": 5.0}


def test_repeated_phase_sums_rather_than_replaces():
    """A resubmission adds to implement time; it does not erase the first attempt."""
    marks = [
        {"phase": "implement", "at": "2026-08-27T10:00:30+00:00", "t0": "2026-08-27T10:00:00+00:00"},
        {"phase": "apply", "at": "2026-08-27T10:00:31+00:00", "t0": "2026-08-27T10:00:00+00:00"},
        {"phase": "implement", "at": "2026-08-27T10:01:01+00:00", "t0": "2026-08-27T10:00:00+00:00"},
    ]
    assert durations(marks)["implement"] == 60.0


def test_edit_stats_read_from_the_submission_itself(tmp_path):
    f = tmp_path / "edits.json"
    f.write_text(json.dumps([
        {"file": "a.toml", "old_string": "x", "new_string": "yy"},
        {"file": "a.toml", "old_string": "p", "new_string": "qqq"},
        {"file": "tests/test_a.py", "old_string": "", "new_string": "def t(): pass"},
    ]))
    assert edit_stats(f) == {"files": 2, "edits": 3, "bytes_changed": 2 + 3 + len("def t(): pass")}


def test_edit_stats_absent_file_reports_unknown_not_zero(tmp_path):
    assert edit_stats(tmp_path / "nope.json") == {"files": None, "edits": None, "bytes_changed": None}


def test_edit_stats_malformed_file_reports_unknown(tmp_path):
    f = tmp_path / "edits.json"
    f.write_text("not json")
    assert edit_stats(f)["edits"] is None


def test_metric_deltas_only_report_what_moved(tmp_path):
    before, after = tmp_path / "b.json", tmp_path / "a.json"
    before.write_text(json.dumps({"per_source": {"forbes": {"schema_f1": 0.0, "integrated_rate": 1.0}}}))
    after.write_text(json.dumps({"per_source": {"forbes": {"schema_f1": 1.0, "integrated_rate": 1.0}}}))
    d = metric_deltas(after, before)
    assert d == {"forbes.schema_f1": {"before": 0.0, "after": 1.0, "delta": 1.0}}


def test_unmeasured_metric_never_becomes_a_zero_delta(tmp_path):
    """value_recall is null on the real split. Treating null as 0.0 would invent
    a regression or an improvement that was never measured."""
    before, after = tmp_path / "b.json", tmp_path / "a.json"
    before.write_text(json.dumps({"per_source": {"forbes": {"schema_f1": 0.0, "value_recall": None}}}))
    after.write_text(json.dumps({"per_source": {"forbes": {"schema_f1": 1.0, "value_recall": None}}}))
    assert "forbes.value_recall" not in metric_deltas(after, before)


def test_metric_deltas_cover_reconcile_metrics(tmp_path):
    before, after = tmp_path / "b.json", tmp_path / "a.json"
    base = {"entity_matching": {"f1": 0.0}, "fusion": {"accuracy": 0.875}}
    before.write_text(json.dumps({"reconcile": base}))
    after.write_text(json.dumps({"reconcile": {"entity_matching": {"f1": 1.0}, "fusion": {"accuracy": 0.875}}}))
    d = metric_deltas(after, before)
    assert d["reconcile.entity_matching_f1"]["delta"] == 1.0
    assert "reconcile.fusion_accuracy" not in d


def test_full_cycle_writes_one_record(cycle):
    assert main(["start", "--cycle", "1"]) == 0
    for phase in ("simulate", "analyze", "gate1", "implement", "apply", "test", "evaluate", "gate2"):
        assert main(["mark", phase]) == 0
    assert main(["finish", "--outcome", "kept"]) == 0

    log = cycle / "runs/delivery/cycles.jsonl"
    (rec,) = records(log)
    assert rec["outcome"] == "kept"
    assert rec["cycle"] == 1
    assert rec["gates"] == "human"
    assert rec["control_stop"] is False
    assert rec["resubmissions"] == 0
    assert set(rec["seconds"]) == {"simulate", "analyze", "gate1", "implement", "apply", "test", "evaluate", "gate2"}
    assert not cycle_log.IN_PROGRESS.exists()


def test_resubmission_is_counted(cycle):
    main(["start", "--cycle", "1"])
    for phase in ("implement", "apply", "implement", "apply", "test", "gate2"):
        main(["mark", phase])
    main(["finish", "--outcome", "kept"])
    (rec,) = records(cycle / "runs/delivery/cycles.jsonl")
    assert rec["resubmissions"] == 1


def test_control_stop_is_flagged(cycle):
    main(["start", "--cycle", "1"])
    main(["mark", "evaluate"])
    main(["finish", "--outcome", "regression-blocked"])
    (rec,) = records(cycle / "runs/delivery/cycles.jsonl")
    assert rec["control_stop"] is True


def test_finish_without_start_is_an_error(cycle):
    with pytest.raises(SystemExit):
        main(["finish", "--outcome", "kept"])


def test_unknown_outcome_is_rejected(cycle):
    main(["start", "--cycle", "1"])
    with pytest.raises(SystemExit):
        main(["finish", "--outcome", "mostly-fine"])


def test_eval_calls_counted_from_the_evaluator_log(cycle, tmp_path):
    log = tmp_path / "eval.jsonl"
    log.write_text('{"a": 1}\n{"a": 2}\n\n')
    main(["start", "--cycle", "1"])
    main(["mark", "evaluate"])
    main(["finish", "--outcome", "kept", "--eval-log", str(log)])
    (rec,) = records(cycle / "runs/delivery/cycles.jsonl")
    assert rec["eval_calls"] == 2


def test_human_seconds_counts_only_the_gates(cycle):
    main(["start", "--cycle", "1"])
    main(["mark", "implement"])
    main(["mark", "gate1"])
    main(["mark", "gate2"])
    main(["finish", "--outcome", "kept"])
    (rec,) = records(cycle / "runs/delivery/cycles.jsonl")
    expected = rec["seconds"]["gate1"] + rec["seconds"]["gate2"]
    assert rec["human_seconds"] == pytest.approx(expected, abs=0.01)


def test_trial_cycles_are_tagged_auto(cycle):
    main(["start", "--cycle", "1", "--gates", "auto", "--trial", "3"])
    main(["mark", "evaluate"])
    main(["finish", "--outcome", "kept"])
    (rec,) = records(cycle / "runs/delivery/cycles.jsonl")
    assert rec["gates"] == "auto" and rec["trial"] == 3


def test_summary_rates_ignore_skipped_cycles():
    recs = [
        {"outcome": "kept", "human_seconds": 60, "total_seconds": 300, "resubmissions": 0, "eval_calls": 2},
        {"outcome": "reverted", "human_seconds": 30, "total_seconds": 200, "resubmissions": 1, "eval_calls": 2},
        {"outcome": "skipped", "human_seconds": 5, "total_seconds": 5},
    ]
    s = summarize(recs)
    assert s["cycles"] == 3
    assert s["decided"] == 2
    assert s["acceptance_rate"] == 0.5
    assert s["human_minutes_per_accepted"] == 1.5
    assert s["first_pass_rate"] == 1.0


def test_summary_with_no_accepted_cycle_reports_none_not_zero():
    s = summarize([{"outcome": "reverted", "human_seconds": 30, "total_seconds": 200}])
    assert s["accepted"] == 0
    assert s["human_minutes_per_accepted"] is None
    assert s["first_pass_rate"] is None


def test_eval_calls_per_accepted_is_none_when_never_measured():
    # No kept cycle here ever passed --eval-log, so eval_calls is None on all
    # of them -- that must report None ("not measured"), never 0.0
    # ("measured, and zero calls happened").
    recs = [
        {"outcome": "kept", "human_seconds": 60, "total_seconds": 300, "eval_calls": None},
        {"outcome": "kept", "human_seconds": 90, "total_seconds": 400, "eval_calls": None},
    ]
    s = summarize(recs)
    assert s["eval_calls_per_accepted"] is None


def test_eval_calls_per_accepted_averages_only_measured_cycles():
    recs = [
        {"outcome": "kept", "human_seconds": 60, "total_seconds": 300, "eval_calls": 2},
        {"outcome": "kept", "human_seconds": 90, "total_seconds": 400, "eval_calls": 4},
    ]
    s = summarize(recs)
    assert s["eval_calls_per_accepted"] == 3.0


def test_report_on_an_empty_log_says_so(cycle, capsys):
    assert main(["report"]) == 0
    assert "No delivery telemetry yet" in capsys.readouterr().out


def test_report_prints_the_headline_economics(cycle, capsys):
    main(["start", "--cycle", "1"])
    main(["mark", "gate2"])
    main(["finish", "--outcome", "kept"])
    capsys.readouterr()
    main(["report"])
    out = capsys.readouterr().out
    assert "Delivery economics" in out
    assert "accepted at Gate 2" in out
