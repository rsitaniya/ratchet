"""Unit tests for the fullcontact adapter's Attribute_3 -> country, Attribute_4 -> city
and Attribute_6 -> founded mappings.

Every raw value below is copied verbatim from data/madi/sources/fullcontact.jsonl.
A mapping that names the right target but normalizes nothing still satisfies a
correspondence check, so each case asserts the value actually produced, and each
absent-value case asserts that no target value is produced at all.
"""
from pathlib import Path

import pytest

from engagements.madi_onboarding import adapters as A
from engagements.madi_onboarding import normalizers as n

ADAPTERS_REAL = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding" / "adapters_real"

# Real records, by Attribute_1.
CIT = {
    "Attribute_1": "fullcontact_2",
    "Attribute_2": "CIT Group Inc (DEL)",
    "Attribute_3": "Canada",
    "Attribute_4": "Toronto",
    "Attribute_5": "",
    "Attribute_6": "1908-01-01",
}
ABB = {
    "Attribute_1": "fullcontact_43",
    "Attribute_2": "ABB Ltd",
    "Attribute_3": "Switzerland",
    "Attribute_4": "Zurich",
    "Attribute_5": "",
    "Attribute_6": "1988-01-01",
}
TELEMACH = {
    "Attribute_1": "fullcontact_1812",
    "Attribute_2": "Telemach BiH",
    "Attribute_3": "Bosnia and Herzegovina",
    "Attribute_4": "Sarajevo",
    "Attribute_5": "",
    "Attribute_6": "2010-01-01",
}
MOES = {
    "Attribute_1": "fullcontact_978",
    "Attribute_2": "MOES SOUTHWEST GRILL",
    "Attribute_3": "United States",
    "Attribute_4": "DURHAM",
    "Attribute_5": "",
    "Attribute_6": "1000-01-01",
}
# Attribute_4 is the four-character string "null", not an absent value.
KYOCERA = {
    "Attribute_1": "fullcontact_13",
    "Attribute_2": "Kyocera Fineceramics Ltd",
    "Attribute_3": "Japan",
    "Attribute_4": "null",
    "Attribute_5": "",
    "Attribute_6": "",
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
# Attribute_3 is the placeholder "Other", which names no country.
THOMSON = {
    "Attribute_1": "fullcontact_35",
    "Attribute_2": "Thomson Reuters Corp",
    "Attribute_3": "Other",
    "Attribute_4": "null",
    "Attribute_5": "",
    "Attribute_6": "",
}


def _apply(rec):
    adapter = A.load_adapter("fullcontact", ADAPTERS_REAL)
    return A.apply_adapter(rec, adapter, {"attributes": {}})


def _invalid(res):
    return {f["field"] for f in res["failures"] if f["error_code"] == "INVALID_VALUE_FORMAT"}


def test_country_maps_a_name_the_seed_table_already_covered():
    assert _apply(CIT)["target"]["country"] == "CA"


def test_country_maps_names_the_seed_table_missed():
    # Switzerland is the largest previously-uncovered country in the export.
    assert _apply(ABB)["target"]["country"] == "CH"
    assert _apply(TELEMACH)["target"]["country"] == "BA"


def test_empty_country_produces_no_value():
    res = _apply(TABBS)
    assert "country" not in res["target"]
    assert "Attribute_3" in _invalid(res)


def test_placeholder_country_other_produces_no_value():
    # "Other" is not a country name, so inventing an ISO code for it would be
    # fabricating data. The record still onboards its other columns.
    res = _apply(THOMSON)
    assert "country" not in res["target"]
    assert res["target"]["name"] == "Thomson Reuters Corp"


def test_city_maps_a_real_value():
    assert _apply(ABB)["target"]["city"] == "Zurich"
    assert _apply(MOES)["target"]["city"] == "DURHAM"


def test_literal_null_city_produces_no_value():
    # The failure this normalizer exists for: `identity` would return "null" and
    # 92 records would be counted as delivering a city they do not have.
    res = _apply(KYOCERA)
    assert "city" not in res["target"]
    assert "Attribute_4" in _invalid(res)


def test_empty_city_produces_no_value():
    res = _apply(TABBS)
    assert "city" not in res["target"]
    assert "Attribute_4" in _invalid(res)


def test_founded_takes_the_year_out_of_an_iso_date():
    assert _apply(CIT)["target"]["founded"] == 1908
    assert _apply(ABB)["target"]["founded"] == 1988
    # 1000 is the oldest year in the export and the floor to_int_year accepts.
    assert _apply(MOES)["target"]["founded"] == 1000


def test_empty_founded_produces_no_value():
    res = _apply(TABBS)
    assert "founded" not in res["target"]
    assert "Attribute_6" in _invalid(res)


def test_iso_date_to_year_rejects_what_is_not_a_date():
    assert n.iso_date_to_year("1908-01-01") == 1908
    for raw in ["", "null", "not-a-date", None]:
        with pytest.raises(ValueError):
            n.iso_date_to_year(raw)


def test_non_empty_text_rejects_blanks_and_the_literal_null():
    assert n.non_empty_text("Toronto") == "Toronto"
    for raw in ["", "   ", "null", None]:
        with pytest.raises(ValueError):
            n.non_empty_text(raw)


def test_new_normalizers_are_registered():
    assert n.get("iso_date_to_year") is n.iso_date_to_year
    assert n.get("non_empty_text") is n.non_empty_text


def test_existing_normalizers_keep_their_contracts():
    # This cycle adds normalizers and table rows; it must not widen the ones the
    # dbpedia and forbes adapters already point at.
    assert n.to_int_year("2009") == 2009
    with pytest.raises(ValueError):
        n.to_int_year("1908-01-01")
    with pytest.raises(ValueError):
        n.country_to_iso("")
    assert n.identity("null") == "null"
