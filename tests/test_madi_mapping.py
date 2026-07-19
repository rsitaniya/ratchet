"""Unit tests for the pure adapter mapping engine."""
import json
from pathlib import Path

import pytest

from engagements.madi_onboarding import adapters as A

FIX = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "fixtures"
ADAPTERS = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "adapters"


def _schema():
    return json.loads((FIX / "target_schema.json").read_text())


def _rows(name):
    return [json.loads(ln) for ln in (FIX / "sources" / name).read_text().splitlines() if ln.strip()]


def test_seed_dbpedia_records_integrate_cleanly():
    schema = _schema()
    adapter = A.load_adapter("dbpedia", ADAPTERS)
    for rec in _rows("dbpedia.jsonl"):
        res = A.apply_adapter(rec, adapter, schema)
        assert res["integrated"], f"{rec['record_id']} should integrate: {res['failures']}"
        assert res["target"]["country"] == rec["hq_country"]  # already ISO-2
        assert isinstance(res["target"]["founded"], int)


def test_unonboarded_forbes_fails_every_record():
    schema = _schema()
    adapter = A.load_adapter("forbes", ADAPTERS)  # empty field map
    for rec in _rows("forbes.jsonl"):
        res = A.apply_adapter(rec, adapter, schema)
        assert not res["integrated"]
        codes = {f["error_code"] for f in res["failures"]}
        assert "UNMAPPED_FIELD" in codes
        assert "MISSING_REQUIRED_FIELD" in codes  # name/founded/country never produced


def test_full_forbes_adapter_integrates_and_normalizes():
    # Simulate the adapter the loop is meant to converge to, and confirm the
    # normalizers do the real work (currency, country, year).
    schema = _schema()
    adapter = {
        "source": "forbes",
        "fields": {
            "name": {"target": "name", "normalizer": "identity"},
            "yearFounded": {"target": "founded", "normalizer": "to_int_year"},
            "country": {"target": "country", "normalizer": "country_to_iso"},
            "city": {"target": "city", "normalizer": "identity"},
            "industry": {"target": "industry", "normalizer": "identity"},
            "assets": {"target": "assets", "normalizer": "currency_to_usd"},
            "sales": {"target": "revenue", "normalizer": "currency_to_usd"},
            "ceo": {"target": "keypeople", "normalizer": "to_list"},
        },
    }
    gold_lines = [json.loads(ln) for ln in (FIX / "gold_records.jsonl").read_text().splitlines() if ln.strip()]
    gold = {g["record_id"]: g for g in gold_lines}
    for rec in _rows("forbes.jsonl"):
        res = A.apply_adapter(rec, adapter, schema)
        assert res["integrated"], res["failures"]
        assert res["target"] == {k: v for k, v in gold[rec["record_id"]].items() if k != "record_id"}


def test_partial_adapter_reports_only_real_gaps():
    # Map name+founded+country (required) but leave 'sales' unmapped: record
    # integrates (required present) but 'sales' is an UNMAPPED_FIELD signal.
    schema = _schema()
    adapter = {
        "source": "forbes",
        "fields": {
            "name": {"target": "name", "normalizer": "identity"},
            "yearFounded": {"target": "founded", "normalizer": "to_int_year"},
            "country": {"target": "country", "normalizer": "country_to_iso"},
        },
    }
    res = A.apply_adapter(_rows("forbes.jsonl")[0], adapter, schema)
    assert res["integrated"]  # all REQUIRED attrs present
    unmapped = {f["field"] for f in res["failures"] if f["error_code"] == "UNMAPPED_FIELD"}
    assert "sales" in unmapped and "assets" in unmapped


def test_bad_value_is_invalid_format_not_missing():
    schema = _schema()
    adapter = {"source": "x", "fields": {
        "name": {"target": "name", "normalizer": "identity"},
        "yearFounded": {"target": "founded", "normalizer": "to_int_year"},
        "country": {"target": "country", "normalizer": "country_to_iso"},
    }}
    rec = {"record_id": "z", "name": "Z", "yearFounded": "not-a-year", "country": "United States"}
    res = A.apply_adapter(rec, adapter, schema)
    codes = [(f["error_code"], f["field"]) for f in res["failures"]]
    assert ("INVALID_VALUE_FORMAT", "yearFounded") in codes
    # 'founded' must NOT also be double-reported as MISSING_REQUIRED_FIELD
    assert ("MISSING_REQUIRED_FIELD", "founded") not in codes


def test_unknown_normalizer_raises_at_load(tmp_path):
    (tmp_path / "bad.toml").write_text('source="bad"\n[fields.x]\ntarget="name"\nnormalizer="nope"\n')
    with pytest.raises(ValueError, match="unknown normalizer"):
        A.load_adapter("bad", tmp_path)
