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
