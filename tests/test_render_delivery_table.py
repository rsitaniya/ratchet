"""The generated delivery-economics region: it must own its contents.

The point of generating this table rather than checking it is that a published
figure cannot be retyped, so these tests are about the round trip and about
--check actually failing on tampering -- a generator whose check passes on edited
output is worse than no generator, because it looks like protection.
"""
import json

import pytest
from render_delivery_table import END, START, main, render, splice

CYCLE = {
    "cycle": 1, "outcome": "kept", "control_stop": False, "resubmissions": 0,
    "total_seconds": 300.0, "agent_seconds": 120.0, "eval_calls": None,
    "metrics": {"src.schema_f1": {"before": 0.0, "after": 0.5, "delta": 0.5}},
}


def _doc(tmp_path, body="stale"):
    d = tmp_path / "DOC.md"
    d.write_text(f"before\n\n{START}\n{body}\n{END}\n\nafter\n")
    return d


def _log(tmp_path, records):
    p = tmp_path / "cycles.jsonl"
    p.write_text("".join(json.dumps(r) + "\n" for r in records))
    return p


def test_write_then_check_round_trips(tmp_path):
    doc, log = _doc(tmp_path), _log(tmp_path, [CYCLE])
    assert main([str(doc), "--log", str(log), "--write"]) == 0
    assert main([str(doc), "--log", str(log), "--check"]) == 0
    text = doc.read_text()
    assert text.startswith("before\n") and text.endswith("after\n")  # markers preserved in place


def test_check_fails_when_a_generated_figure_is_edited(tmp_path):
    doc, log = _doc(tmp_path), _log(tmp_path, [CYCLE])
    main([str(doc), "--log", str(log), "--write"])
    doc.write_text(doc.read_text().replace("2.0", "9.9"))  # agent minutes 120s -> 2.0
    assert main([str(doc), "--log", str(log), "--check"]) == 1


def test_check_fails_when_a_new_cycle_lands(tmp_path):
    doc, log = _doc(tmp_path), _log(tmp_path, [CYCLE])
    main([str(doc), "--log", str(log), "--write"])
    log2 = _log(tmp_path, [CYCLE, {**CYCLE, "cycle": 2}])
    assert main([str(doc), "--log", str(log2), "--check"]) == 1


def test_unmeasured_eval_calls_never_render_as_zero(tmp_path):
    body = render([CYCLE])
    assert "not measured" in body
    assert "| Evaluator calls per accepted change | 0 |" not in body


def test_render_reports_agent_and_wall_time_but_no_human_time(tmp_path):
    body = render([CYCLE])
    assert "Agent minutes per accepted change | 2.0" in body
    assert "Wall minutes per accepted change (incl. gates) | 5.0" in body
    assert "uman" not in body  # no "Human"/"human" time figure, ever


def test_splice_refuses_a_doc_with_no_region(tmp_path):
    with pytest.raises(SystemExit):
        splice("no markers here", "body")


def test_missing_log_is_an_error_not_an_empty_table(tmp_path):
    doc = _doc(tmp_path)
    assert main([str(doc), "--log", str(tmp_path / "nope.jsonl"), "--check"]) == 1
    assert main([str(doc), "--log", str(_log(tmp_path, [])), "--check"]) == 1
