"""Tests for the MaDI-Bench CSV → ingest-JSONL converter.

No network and no real benchmark data — a small synthetic CSV exercises the
same mechanics (header-driven columns, empty cells, embedded commas) that the
real dbpedia/forbes/fullcontact exports have, so this passes without
`download_data.py` ever having run.
"""
import json

import pytest

from engagements.madi_onboarding import csv_to_ingest as C


def _write_csv(path, text):
    path.write_text(text, encoding="utf-8")


def test_rows_become_jsonl_with_columns_verbatim(tmp_path):
    inp = tmp_path / "forbes.csv"
    out = tmp_path / "forbes.jsonl"
    _write_csv(inp, "company,region,sales_figure\nAcme Corp,US,1000\n")
    C.main(["--input", str(inp), "--output", str(out)])
    records = [json.loads(ln) for ln in out.read_text().splitlines()]
    assert records == [{"company": "Acme Corp", "region": "US", "sales_figure": "1000"}]


def test_empty_cell_becomes_empty_string_not_dropped(tmp_path):
    # A real MaDI-Bench row often has a blank cell (e.g. dbpedia's missing
    # total_assets_val) — the column must still be present, as "".
    inp = tmp_path / "dbpedia.csv"
    out = tmp_path / "dbpedia.jsonl"
    _write_csv(inp, "org_name,total_assets_val\nAcme Corp,\n")
    C.main(["--input", str(inp), "--output", str(out)])
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec == {"org_name": "Acme Corp", "total_assets_val": ""}


def test_embedded_comma_and_quote_survive_csv_quoting(tmp_path):
    # A real company name can carry a comma ("Acme, Inc.") — RFC 4180 quoting
    # must round-trip through csv.DictReader, not split into extra fields.
    inp = tmp_path / "forbes.csv"
    out = tmp_path / "forbes.jsonl"
    _write_csv(inp, 'company,region\n"Acme, Inc.",US\n')
    C.main(["--input", str(inp), "--output", str(out)])
    rec = json.loads(out.read_text().splitlines()[0])
    assert rec["company"] == "Acme, Inc."


def test_multiple_rows_preserve_order_and_count(tmp_path):
    inp = tmp_path / "forbes.csv"
    out = tmp_path / "forbes.jsonl"
    _write_csv(inp, "company\nFirst\nSecond\nThird\n")
    C.main(["--input", str(inp), "--output", str(out)])
    companies = [json.loads(ln)["company"] for ln in out.read_text().splitlines()]
    assert companies == ["First", "Second", "Third"]


def test_header_only_csv_fails_loud_not_a_silent_empty_output(tmp_path):
    # Zero data rows is a real upstream failure mode (a truncated download, a
    # wrong file) — CLAUDE.md rule 15: fail visibly, not with a quiet 0-line file.
    inp = tmp_path / "forbes.csv"
    out = tmp_path / "forbes.jsonl"
    _write_csv(inp, "company,region\n")
    with pytest.raises(SystemExit, match="no data rows"):
        C.main(["--input", str(inp), "--output", str(out)])


def test_default_paths_are_source_named_under_data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "DATA_DIR", tmp_path)
    _write_csv(tmp_path / "forbes.csv", "company\nAcme\n")
    C.main(["--source", "forbes"])
    assert (tmp_path / "forbes.jsonl").exists()
