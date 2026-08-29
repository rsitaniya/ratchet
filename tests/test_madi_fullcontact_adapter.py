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
    # Attribute_5 was abridged here while this column was unmapped; it is the
    # source's full seven-name list, including its own near-duplicate entry.
    {"Attribute_1": "fullcontact_985", "Attribute_2": "Wix.com Ltd.", "Attribute_3": "Israel",
     "Attribute_4": "Tel Aviv",
     "Attribute_5": "['Angel Fuentes', 'Avishai Abrahami', 'Dr. Eric Johnson', 'Giora Kaplan', "
                    "'Giora Kaplan (Gig)', 'Nadav Abrahami', 'Richard Oldale']",
     "Attribute_6": "2006-01-01"},
    {"Attribute_1": "fullcontact_4", "Attribute_2": "Ingersoll Rand South East Asia (Pte) Ltd",
     "Attribute_3": "Ireland", "Attribute_4": "Swords", "Attribute_5": "",
     "Attribute_6": "1871-01-01"},
    {"Attribute_1": "fullcontact_13", "Attribute_2": "Kyocera Fineceramics Ltd", "Attribute_3": "Japan",
     "Attribute_4": "null", "Attribute_5": "", "Attribute_6": ""},
    {"Attribute_1": "fullcontact_35", "Attribute_2": "Thomson Reuters Corp", "Attribute_3": "Other",
     "Attribute_4": "null", "Attribute_5": "", "Attribute_6": ""},
    {"Attribute_1": "fullcontact_102", "Attribute_2": "Apple Inc.", "Attribute_3": "United States",
     "Attribute_4": "Cupertino", "Attribute_5": "['Ron Wayne', 'Steve Jobs', 'Steve Wozniak']",
     "Attribute_6": ""},
    {"Attribute_1": "fullcontact_150", "Attribute_2": "Bharat Petroleum Corporation Limited",
     "Attribute_3": "India", "Attribute_4": "Mumbai", "Attribute_5": "Anand Bhaskar, PCC",
     "Attribute_6": "1977-01-01"},
]


def _adapter():
    return A.load_adapter("fullcontact", ADAPTERS_REAL)


def test_adapter_produces_id_and_name_for_every_real_record():
    adapter = _adapter()
    for rec in REAL_RECORDS:
        res = A.apply_adapter(rec, adapter, SCHEMA)
        assert res["target"]["id"] == rec["Attribute_1"], res["failures"]
        assert res["target"]["name"] == rec["Attribute_2"], res["failures"]


def test_full_target_for_a_record_with_no_founding_date():
    # Attribute_6 is empty here, so founded is the only mapped attribute that
    # cannot be produced; id, name, country, city and keypeople all land.
    res = A.apply_adapter(REAL_RECORDS[0], _adapter(), SCHEMA)
    assert res["target"] == {
        "id": "fullcontact_1", "name": "BBMG", "country": "US", "city": "Brooklyn",
        "keypeople": ["Raphael Bemporad"],
    }


def test_non_ascii_name_passes_through_unchanged():
    res = A.apply_adapter(REAL_RECORDS[2], _adapter(), SCHEMA)
    assert res["target"]["name"] == "Hermès"


def test_country_city_and_founded_now_land_and_three_attributes_remain_unmapped():
    res = A.apply_adapter(REAL_RECORDS[1], _adapter(), SCHEMA)
    assert res["target"] == {
        "id": "fullcontact_2", "name": "CIT Group Inc (DEL)", "country": "CA",
        "city": "Toronto", "founded": 1908,
    }
    missing = {f["field"] for f in res["failures"] if f["error_code"] == "MISSING_REQUIRED_FIELD"}
    assert missing == {"industry", "assets", "revenue"}
    unmapped = {f["field"] for f in res["failures"] if f["error_code"] == "UNMAPPED_FIELD"}
    assert unmapped == set()  # every column fullcontact carries is now mapped
    assert not res["integrated"]  # no source column carries industry/assets/revenue


def test_absent_name_is_an_invalid_value_not_a_missing_field():
    # identity() raises on None, so a null name must surface against the mapped
    # column rather than look like an attribute nobody mapped.
    rec = dict(REAL_RECORDS[0], Attribute_2=None)
    res = A.apply_adapter(rec, _adapter(), SCHEMA)
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "Attribute_2") in codes
    assert ("MISSING_REQUIRED_FIELD", "name") not in codes


def test_iso_founding_dates_become_years():
    for rec, year in [(REAL_RECORDS[1], 1908), (REAL_RECORDS[2], 1837),
                      (REAL_RECORDS[3], 2006), (REAL_RECORDS[4], 1871)]:
        res = A.apply_adapter(rec, _adapter(), SCHEMA)
        assert res["target"]["founded"] == year, res["failures"]


def test_empty_founding_date_is_an_invalid_value_not_a_year():
    res = A.apply_adapter(REAL_RECORDS[0], _adapter(), SCHEMA)
    assert "founded" not in res["target"]
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "Attribute_6") in codes


def test_country_names_beyond_the_seed_table_resolve():
    for rec, iso in [(REAL_RECORDS[3], "IL"), (REAL_RECORDS[4], "IE"), (REAL_RECORDS[5], "JP")]:
        res = A.apply_adapter(rec, _adapter(), SCHEMA)
        assert res["target"]["country"] == iso, res["failures"]


def test_the_catch_all_country_other_produces_no_country():
    # "Other" is the source's own bucket for "not one of the countries I track".
    # Emitting it as a country would be a value nothing can reconcile against.
    res = A.apply_adapter(REAL_RECORDS[6], _adapter(), SCHEMA)
    assert "country" not in res["target"]
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "Attribute_3") in codes


def test_real_city_values_pass_through():
    for rec, city in [(REAL_RECORDS[0], "Brooklyn"), (REAL_RECORDS[3], "Tel Aviv"),
                      (REAL_RECORDS[4], "Swords")]:
        res = A.apply_adapter(rec, _adapter(), SCHEMA)
        assert res["target"]["city"] == city, res["failures"]


def test_literal_null_city_does_not_become_a_city():
    # 92 of the 1931 records hold the four-character string "null" in Attribute_4.
    # identity would emit it as a city and report a yield that isn't real.
    res = A.apply_adapter(REAL_RECORDS[5], _adapter(), SCHEMA)
    assert "city" not in res["target"]
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "Attribute_4") in codes


def test_empty_country_and_city_produce_nothing():
    res = A.apply_adapter(REAL_RECORDS[2], _adapter(), SCHEMA)
    assert res["target"] == {"id": "fullcontact_12", "name": "Hermès", "founded": 1837}
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "Attribute_3") in codes
    assert ("INVALID_VALUE_FORMAT", "Attribute_4") in codes


def test_a_single_name_becomes_a_one_element_keypeople_list():
    # 120 of the 1931 records carry one name as plain text.
    for rec, people in [(REAL_RECORDS[0], ["Raphael Bemporad"]),
                        (REAL_RECORDS[8], ["Anand Bhaskar, PCC"])]:
        res = A.apply_adapter(rec, _adapter(), SCHEMA)
        assert res["target"]["keypeople"] == people, res["failures"]


def test_a_printed_python_list_becomes_the_names_it_holds():
    # 72 records store this column as a printed list. to_list would have emitted
    # the whole rendered string as a single name.
    res = A.apply_adapter(REAL_RECORDS[7], _adapter(), SCHEMA)
    assert res["target"]["keypeople"] == ["Ron Wayne", "Steve Jobs", "Steve Wozniak"], res["failures"]
    res = A.apply_adapter(REAL_RECORDS[3], _adapter(), SCHEMA)
    assert res["target"]["keypeople"] == [
        "Angel Fuentes", "Avishai Abrahami", "Dr. Eric Johnson", "Giora Kaplan",
        "Giora Kaplan (Gig)", "Nadav Abrahami", "Richard Oldale",
    ], res["failures"]


def test_empty_keypeople_is_an_invalid_value_not_a_one_element_list():
    # 1739 of the 1931 records are empty here; to_list would have emitted [""]
    # and reported a yield of 1.0 on a column with 192 real values.
    res = A.apply_adapter(REAL_RECORDS[1], _adapter(), SCHEMA)
    assert "keypeople" not in res["target"]
    codes = {(f["error_code"], f["field"]) for f in res["failures"]}
    assert ("INVALID_VALUE_FORMAT", "Attribute_5") in codes


def test_missing_keypeople_never_blocks_integration():
    # keypeople is the one optional target; an empty Attribute_5 must not add a
    # MISSING_REQUIRED_FIELD failure the way an unmapped required attribute does.
    res = A.apply_adapter(REAL_RECORDS[1], _adapter(), SCHEMA)
    missing = {f["field"] for f in res["failures"] if f["error_code"] == "MISSING_REQUIRED_FIELD"}
    assert "keypeople" not in missing
