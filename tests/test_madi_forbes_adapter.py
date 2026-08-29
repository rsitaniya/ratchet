"""Unit tests for the real forbes split's adapter (adapters_real/forbes.toml).

Records are copied verbatim from data/madi/sources/forbes.jsonl. That data is
gitignored, so values are inlined here rather than read at test time — the
adapter TOML itself is committed and is loaded for real.

id is deliberately not covered by a "lands" assertion: apply_adapter() skips
the literal "record_id" key unconditionally (adapters.py), so no adapter entry
can ever map it for this source. See LIMITS in the change that added this file.
"""
from pathlib import Path

from engagements.madi_onboarding import adapters as A

ADAPTERS_REAL = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "adapters_real"

# The real split's target schema (data/madi/target_schema.json): everything
# except keypeople is required.
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
    {"forbes_url": "http://www.forbes.com/companies/icbc/", "company": "ICBC",
     "url": "http://www.forbes.com/companies/icbc/", "region": "China",
     "business_segment": "Major Banks", "asset_value": "3124900000000",
     "sales_figure": "148700000000"},
    {"forbes_url": "http://www.forbes.com/companies/berkshire-hathaway/",
     "company": "Berkshire Hathaway",
     "url": "http://www.forbes.com/companies/berkshire-hathaway/",
     "region": "United States of America", "business_segment": "Investment Services",
     "asset_value": "493400000000", "sales_figure": "178800000000"},
]


def _adapter():
    return A.load_adapter("forbes", ADAPTERS_REAL)


def test_name_assets_and_revenue_land_for_a_real_record():
    res = A.apply_adapter(REAL_RECORDS[0], _adapter(), SCHEMA)
    assert res["target"]["name"] == "ICBC", res["failures"]
    assert res["target"]["assets"] == 3124900000000.0, res["failures"]
    assert res["target"]["revenue"] == 148700000000.0, res["failures"]


def test_a_second_real_record_maps_the_same_three_fields():
    res = A.apply_adapter(REAL_RECORDS[1], _adapter(), SCHEMA)
    assert res["target"]["name"] == "Berkshire Hathaway", res["failures"]
    assert res["target"]["assets"] == 493400000000.0, res["failures"]
    assert res["target"]["revenue"] == 178800000000.0, res["failures"]


def test_record_id_is_never_mapped_to_id_even_when_present():
    # apply_adapter() skips the literal "record_id" key unconditionally
    # (adapters.py), so even a real /ingest record carrying it never produces
    # "id" through this adapter's field map — id is out of scope this cycle.
    rec = dict(REAL_RECORDS[0], record_id="forbes-0")
    res = A.apply_adapter(rec, _adapter(), SCHEMA)
    assert "id" not in res["target"]
    missing = {f["field"] for f in res["failures"] if f["error_code"] == "MISSING_REQUIRED_FIELD"}
    assert "id" in missing


def test_malformed_asset_value_raises_invalid_value_not_silently_dropped():
    rec = dict(REAL_RECORDS[0], asset_value="N/A")
    res = A.apply_adapter(rec, _adapter(), SCHEMA)
    assert "assets" not in res["target"]
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "asset_value") in codes


def test_missing_sales_figure_is_an_invalid_value_not_a_silent_pass():
    rec = dict(REAL_RECORDS[0], sales_figure="")
    res = A.apply_adapter(rec, _adapter(), SCHEMA)
    assert "revenue" not in res["target"]
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "sales_figure") in codes
