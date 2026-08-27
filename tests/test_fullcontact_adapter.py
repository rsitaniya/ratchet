"""Unit test for the fullcontact adapter's Attribute_2 -> name mapping."""
from pathlib import Path

from engagements.madi_onboarding import adapters as A

ADAPTERS_REAL = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "adapters_real"


def test_fullcontact_attribute_2_maps_to_name():
    # No required attrs asserted here: this test targets the one mapping this
    # cycle adds, not full-record integration against the held-out gold schema.
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_1",
        "Attribute_2": "BBMG",
        "Attribute_3": "United States",
        "Attribute_4": "Brooklyn",
        "Attribute_5": "",
        "Attribute_6": "",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert res["target"]["name"] == "BBMG"


def test_fullcontact_attribute_1_maps_to_id():
    # No required attrs asserted here: this test targets the one mapping this
    # cycle adds, not full-record integration against the held-out gold schema.
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_1",
        "Attribute_2": "BBMG",
        "Attribute_3": "United States",
        "Attribute_4": "Brooklyn",
        "Attribute_5": "",
        "Attribute_6": "",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert res["target"]["id"] == "fullcontact_1"


def test_fullcontact_attribute_3_maps_to_country_via_country_to_iso():
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_1",
        "Attribute_2": "BBMG",
        "Attribute_3": "United States",
        "Attribute_4": "Brooklyn",
        "Attribute_5": "",
        "Attribute_6": "",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert res["target"]["country"] == "US"


def test_fullcontact_attribute_3_empty_country_is_invalid_value_format():
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_2",
        "Attribute_2": "Acme",
        "Attribute_3": "",
        "Attribute_4": "",
        "Attribute_5": "",
        "Attribute_6": "",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert "country" not in res["target"]
    assert {
        "stage": "value_normalization",
        "error_code": "INVALID_VALUE_FORMAT",
        "field": "Attribute_3",
    } in res["failures"]


def test_fullcontact_attribute_4_maps_to_city_via_identity():
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_1",
        "Attribute_2": "BBMG",
        "Attribute_3": "United States",
        "Attribute_4": "Brooklyn",
        "Attribute_5": "",
        "Attribute_6": "",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert res["target"]["city"] == "Brooklyn"


def test_fullcontact_attribute_6_bare_year_maps_to_founded_via_to_int_year():
    # to_int_year does int(str(raw).strip()) -- it accepts a bare year string,
    # not a full ISO date (see the next test for that case).
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_1",
        "Attribute_2": "BBMG",
        "Attribute_3": "United States",
        "Attribute_4": "Brooklyn",
        "Attribute_5": "",
        "Attribute_6": "1908",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert res["target"]["founded"] == 1908


def test_fullcontact_attribute_6_full_iso_date_is_invalid_value_format():
    # Real fullcontact rows store Attribute_6 as a full ISO date (e.g.
    # "1908-01-01"). to_int_year can't parse that -- it raises ValueError, so
    # the record correctly gets an INVALID_VALUE_FORMAT failure for founded
    # rather than silently truncating to a year (there's no transform hook in
    # the adapter format, and normalizers.py is out of scope this cycle).
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_1",
        "Attribute_2": "BBMG",
        "Attribute_3": "United States",
        "Attribute_4": "Brooklyn",
        "Attribute_5": "",
        "Attribute_6": "1908-01-01",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert "founded" not in res["target"]
    assert {
        "stage": "value_normalization",
        "error_code": "INVALID_VALUE_FORMAT",
        "field": "Attribute_6",
    } in res["failures"]
