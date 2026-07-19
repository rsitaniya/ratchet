"""Tests for the engagement analyzer's gap ranking."""
from engagements.madi_onboarding import analyze_integration as AI


def _gap(field, h, run="r1"):
    return {"event": "integration", "source_system": "forbes", "error_code": "UNMAPPED_FIELD",
            "field": field, "record_id_hash": h, "run_id": run}


def _rec(h, integrated, run="r1"):
    return {"event": "record", "source_system": "forbes", "integrated": integrated,
            "record_id_hash": h, "run_id": run}


def _rows():
    # forbes: 3 records, all fail in run r1; 'sales' unmapped on all 3, 'assets' on 2.
    return [
        _gap("sales", "h1"), _gap("sales", "h2"), _gap("sales", "h3"),
        _gap("assets", "h1"), _gap("assets", "h2"),
        _rec("h1", False), _rec("h2", False), _rec("h3", False),
        _rec("h1", True, run="r2"),  # a later run where forbes now integrates
        {"event": "http", "path": "/ingest", "status_code": 422},  # ignored
    ]


def test_gaps_ranked_by_affected_records():
    rep = AI.summarize(_rows(), run_id="r1")
    assert rep["gaps"][0] == {
        "source_system": "forbes", "error_code": "UNMAPPED_FIELD", "field": "sales", "affected_records": 3,
    }
    assert rep["gaps"][1]["field"] == "assets" and rep["gaps"][1]["affected_records"] == 2


def test_integration_rate_per_source_and_run():
    assert AI.summarize(_rows(), run_id="r1")["sources"]["forbes"]["integrated_rate"] == 0.0
    assert AI.summarize(_rows(), run_id="r2")["sources"]["forbes"]["integrated_rate"] == 1.0


def test_distinct_records_not_double_counted():
    # 'sales' appears 3x across 3 distinct records → 3, not double-counted.
    rep = AI.summarize(_rows(), run_id="r1", source="forbes")
    sales = next(g for g in rep["gaps"] if g["field"] == "sales")
    assert sales["affected_records"] == 3
