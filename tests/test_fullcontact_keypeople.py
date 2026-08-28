"""Unit tests for the fullcontact adapter's Attribute_5 -> keypeople mapping.

Every raw value below is copied verbatim from data/madi/sources/fullcontact.jsonl.
Attribute_5 has exactly three shapes there: "" (1739 of 1931 records), a bare person
name (120), and a stringified Python list literal (72). Only the last two are values,
so each case asserts the list actually produced, and the empty case asserts that no
target value is produced at all.
"""
from pathlib import Path

import pytest

from engagements.madi_onboarding import adapters as A
from engagements.madi_onboarding import normalizers as n

ADAPTERS_REAL = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "adapters_real"

# Real records, by Attribute_1.
BBMG = {
    "Attribute_1": "fullcontact_1",
    "Attribute_2": "BBMG",
    "Attribute_3": "United States",
    "Attribute_4": "Brooklyn",
    "Attribute_5": "Raphael Bemporad",
    "Attribute_6": "",
}
# Attribute_5 is one person carrying a credential, not two names.
BHARAT = {
    "Attribute_1": "fullcontact_150",
    "Attribute_2": "Bharat Petroleum Corporation Limited",
    "Attribute_3": "India",
    "Attribute_4": "Mumbai",
    "Attribute_5": "Anand Bhaskar, PCC",
    "Attribute_6": "1977-01-01",
}
APPLE = {
    "Attribute_1": "fullcontact_102",
    "Attribute_2": "Apple Inc.",
    "Attribute_3": "United States",
    "Attribute_4": "Cupertino",
    "Attribute_5": "['Ron Wayne', 'Steve Jobs', 'Steve Wozniak']",
    "Attribute_6": "",
}
# Two of the three list elements contain a comma of their own.
ACCELERATED = {
    "Attribute_1": "fullcontact_307",
    "Attribute_2": "Accelerated Sciences",
    "Attribute_3": "Italy",
    "Attribute_4": "Torino",
    "Attribute_5": "['Integrated Concepts Vehicles', 'Motorious Motors, llc', 'Motorious, Inc.']",
    "Attribute_6": "",
}
# The longest list in the export (7 elements). One source line, wrapped for line length.
WIX = {
    "Attribute_1": "fullcontact_824",
    "Attribute_2": "Wix.com Ltd.",
    "Attribute_3": "Israel",
    "Attribute_4": "Tel Aviv",
    "Attribute_5": (
        "['Angel Fuentes', 'Avishai Abrahami', 'Dr. Eric Johnson', 'Giora Kaplan', "
        "'Giora Kaplan (Gig)', 'Nadav Abrahami', 'Richard Oldale']"
    ),
    "Attribute_6": "2006-01-01",
}
# Every mappable column is the empty string.
TABBS = {
    "Attribute_1": "fullcontact_10",
    "Attribute_2": "Tabbs",
    "Attribute_3": "",
    "Attribute_4": "",
    "Attribute_5": "",
    "Attribute_6": "",
}


def _apply(rec):
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    return A.apply_adapter(rec, adapter, {"attributes": {}})


def _invalid(res):
    return {f["field"] for f in res["failures"] if f["error_code"] == "INVALID_VALUE_FORMAT"}


def test_keypeople_wraps_a_plain_name_in_a_one_element_list():
    assert _apply(BBMG)["target"]["keypeople"] == ["Raphael Bemporad"]


def test_keypeople_does_not_split_a_plain_name_on_its_comma():
    # Only the bracketed shape is a list; a comma inside a scalar is part of the name.
    assert _apply(BHARAT)["target"]["keypeople"] == ["Anand Bhaskar, PCC"]


def test_keypeople_parses_a_stringified_python_list_into_its_names():
    # to_list returns the raw one-element ["['Ron Wayne', ...]"] here, which is why
    # this column needed its own normalizer.
    assert _apply(APPLE)["target"]["keypeople"] == ["Ron Wayne", "Steve Jobs", "Steve Wozniak"]


def test_keypeople_keeps_commas_that_belong_to_a_list_element():
    assert _apply(ACCELERATED)["target"]["keypeople"] == [
        "Integrated Concepts Vehicles",
        "Motorious Motors, llc",
        "Motorious, Inc.",
    ]


def test_keypeople_parses_the_longest_list_in_the_export():
    assert _apply(WIX)["target"]["keypeople"] == [
        "Angel Fuentes",
        "Avishai Abrahami",
        "Dr. Eric Johnson",
        "Giora Kaplan",
        "Giora Kaplan (Gig)",
        "Nadav Abrahami",
        "Richard Oldale",
    ]


def test_empty_keypeople_produces_no_value():
    # The failure this normalizer exists for: to_list returns [""] on an empty value,
    # so all 1739 empty records would count as delivering key people and yield would
    # read 1.00 instead of the true 192/1931.
    res = _apply(TABBS)
    assert "keypeople" not in res["target"]
    assert "Attribute_5" in _invalid(res)


def test_mapping_keypeople_leaves_the_other_columns_alone():
    res = _apply(APPLE)
    assert res["target"]["id"] == "fullcontact_102"
    assert res["target"]["name"] == "Apple Inc."
    assert res["target"]["country"] == "US"
    assert res["target"]["city"] == "Cupertino"


def test_to_text_list_rejects_blanks_and_shapes_it_cannot_parse():
    assert n.to_text_list("Raphael Bemporad") == ["Raphael Bemporad"]
    # An unparseable or value-less bracketed string raises instead of degrading to a
    # one-element list holding the raw text.
    for raw in ["", "   ", "null", None, "['Steve Jobs'", "[]", "['']"]:
        with pytest.raises(ValueError):
            n.to_text_list(raw)


def test_new_normalizer_is_registered():
    assert n.get("to_text_list") is n.to_text_list


def test_to_list_keeps_its_contract():
    # dbpedia's key_people -> keypeople mapping still points at to_list. This cycle
    # adds a normalizer beside it; widening it would regress that source. The [""]
    # below is exactly the behavior fullcontact must not use.
    assert n.to_list("Dana Reyes") == ["Dana Reyes"]
    assert n.to_list(["A", "B"]) == ["A", "B"]
    assert n.to_list("") == [""]
    with pytest.raises(ValueError):
        n.to_list(None)
