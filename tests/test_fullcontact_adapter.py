"""Unit tests for the fullcontact adapter's Attribute_1 -> id / Attribute_2 -> name mappings."""
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


def test_fullcontact_has_no_unmapped_columns_left():
    # Attribute_1/Attribute_2 were the UNMAPPED_FIELD signal an earlier cycle acted
    # on. Attribute_5 (key people) was the last column out of scope; now that it is
    # mapped, this source reports no unmapped column at all.
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_17",
        "Attribute_2": "Renault",
        "Attribute_3": "France",
        "Attribute_4": "Boulogne Billancourt Cedex",
        "Attribute_5": "['Fernand Renault', 'Louis Renault', 'Marcel Renault']",
        "Attribute_6": "1932-01-01",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert res["target"]["id"] == "fullcontact_17"
    assert res["target"]["name"] == "Renault"
    assert res["target"]["keypeople"] == ["Fernand Renault", "Louis Renault", "Marcel Renault"]
    unmapped = {f["field"] for f in res["failures"] if f["error_code"] == "UNMAPPED_FIELD"}
    assert unmapped == set()


def test_fullcontact_identity_columns_produce_values_on_a_sparse_record():
    # fullcontact_10 has every other column empty; id and name still produce a
    # value, which is the yield this mapping claims.
    schema = {"attributes": {}}
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    rec = {
        "Attribute_1": "fullcontact_10",
        "Attribute_2": "Tabbs",
        "Attribute_3": "",
        "Attribute_4": "",
        "Attribute_5": "",
        "Attribute_6": "",
    }
    res = A.apply_adapter(rec, adapter, schema)
    assert res["target"] == {"id": "fullcontact_10", "name": "Tabbs"}
