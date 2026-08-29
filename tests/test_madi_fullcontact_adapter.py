"""Unit tests for the real fullcontact split's adapter (adapters_real/fullcontact.toml).

Records are copied verbatim from data/madi/sources/fullcontact.jsonl. That data is
CC BY-NC-ND and gitignored, so the values are inlined here rather than read at test
time — the adapter TOML itself is committed and is loaded for real.
"""
from pathlib import Path

from engagements.madi_onboarding import adapters as A

ADAPTERS_REAL = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "adapters_real"

# The real split's target schema (data/madi/target_schema.json): everything except
# keypeople is required.
SCHEMA = {
    "attributes": {
        "id": {"required": True},
        "name": {"required": True},
        "founded": {"required": True},
        "country": {"required": True},
        "city": {"required": True},
        "industry": {"required": True},
        "assets": {"required": True},
        "revenue": {"required": True},
        "keypeople": {"required": False},
    }
}

REAL_RECORDS = [
    {"Attribute_1": "fullcontact_1", "Attribute_2": "BBMG", "Attribute_3": "United States",
     "Attribute_4": "Brooklyn", "Attribute_5": "Raphael Bemporad", "Attribute_6": ""},
    {"Attribute_1": "fullcontact_2", "Attribute_2": "CIT Group Inc (DEL)", "Attribute_3": "Canada",
     "Attribute_4": "Toronto", "Attribute_5": "", "Attribute_6": "1908-01-01"},
    {"Attribute_1": "fullcontact_12", "Attribute_2": "Hermès", "Attribute_3": "",
     "Attribute_4": "", "Attribute_5": "", "Attribute_6": "1837-01-01"},
    {"Attribute_1": "fullcontact_985", "Attribute_2": "Wix.com Ltd.", "Attribute_3": "Israel",
     "Attribute_4": "Tel Aviv", "Attribute_5": "['Avishai Abrahami', 'Nadav Abrahami']",
     "Attribute_6": "2006-01-01"},
]


def _adapter():
    return A.load_adapter("fullcontact", ADAPTERS_REAL)


def test_adapter_produces_id_and_name_for_every_real_record():
    adapter = _adapter()
    for rec in REAL_RECORDS:
        res = A.apply_adapter(rec, adapter, SCHEMA)
        assert res["target"]["id"] == rec["Attribute_1"], res["failures"]
        assert res["target"]["name"] == rec["Attribute_2"], res["failures"]


def test_mapped_values_are_the_exact_source_strings():
    res = A.apply_adapter(REAL_RECORDS[0], _adapter(), SCHEMA)
    assert res["target"] == {"id": "fullcontact_1", "name": "BBMG"}


def test_non_ascii_name_passes_through_unchanged():
    res = A.apply_adapter(REAL_RECORDS[2], _adapter(), SCHEMA)
    assert res["target"]["name"] == "Hermès"


def test_id_and_name_are_no_longer_missing_but_the_rest_still_are():
    res = A.apply_adapter(REAL_RECORDS[1], _adapter(), SCHEMA)
    missing = {f["field"] for f in res["failures"] if f["error_code"] == "MISSING_REQUIRED_FIELD"}
    assert missing == {"founded", "country", "city", "industry", "assets", "revenue"}
    unmapped = {f["field"] for f in res["failures"] if f["error_code"] == "UNMAPPED_FIELD"}
    assert unmapped == {"Attribute_3", "Attribute_4", "Attribute_5", "Attribute_6"}
    assert not res["integrated"]  # six required attributes remain unmapped


def test_absent_name_is_an_invalid_value_not_a_missing_field():
    # identity() raises on None, so a null name must surface against the mapped
    # column rather than look like an attribute nobody mapped.
    rec = dict(REAL_RECORDS[0], Attribute_2=None)
    res = A.apply_adapter(rec, _adapter(), SCHEMA)
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "Attribute_2") in codes
    assert ("MISSING_REQUIRED_FIELD", "name") not in codes
