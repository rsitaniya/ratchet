"""Tests for the protected held-out evaluator (the semantic oracle)."""
import json
import tomllib
from pathlib import Path

from engagements.madi_onboarding import evaluate as E

ENG = Path(__file__).resolve().parent.parent / "engagements" / "madi_onboarding"
FIX = ENG / "fixtures"
SEED_ADAPTERS = ENG / "adapters"

FULL_FORBES = """source = "forbes"
[fields.name]
target = "name"
normalizer = "identity"
[fields.yearFounded]
target = "founded"
normalizer = "to_int_year"
[fields.country]
target = "country"
normalizer = "country_to_iso"
[fields.city]
target = "city"
normalizer = "identity"
[fields.industry]
target = "industry"
normalizer = "identity"
[fields.assets]
target = "assets"
normalizer = "currency_to_usd"
[fields.sales]
target = "revenue"
normalizer = "currency_to_usd"
[fields.ceo]
target = "keypeople"
normalizer = "to_list"
"""


def _adapters_with_forbes(tmp_path, forbes_toml: str) -> Path:
    d = tmp_path / "adapters"
    d.mkdir()
    (d / "dbpedia.toml").write_text((SEED_ADAPTERS / "dbpedia.toml").read_text())
    (d / "forbes.toml").write_text(forbes_toml)
    return d


def test_seed_state_dbpedia_perfect_forbes_zero():
    # With the committed seed adapters: dbpedia fully integrates, forbes is
    # unonboarded (empty adapter) so it scores zero across the board.
    res = E.evaluate(["dbpedia", "forbes"], FIX, SEED_ADAPTERS)
    db = res["per_source"]["dbpedia"]
    fb = res["per_source"]["forbes"]
    assert db["fully_correct_rate"] == 1.0 and db["schema_f1"] == 1.0
    assert fb["schema_f1"] == 0.0 and fb["fully_correct_rate"] == 0.0
    assert fb["integrated_rate"] == 0.0


def test_full_forbes_adapter_scores_high_against_gold(tmp_path):
    adir = _adapters_with_forbes(tmp_path, FULL_FORBES)
    res = E.evaluate(["forbes"], FIX, adir)
    fb = res["per_source"]["forbes"]
    assert fb["schema_f1"] == 1.0
    assert fb["value_recall"] == 1.0
    assert fb["fully_correct_rate"] == 1.0  # value normalizers all correct vs gold


def test_wrong_mapping_lowers_schema_f1_and_values(tmp_path):
    # Map 'sales' to the WRONG target (assets instead of revenue): schema F1 and
    # value accuracy both drop — the oracle catches a plausible-but-wrong adapter.
    wrong = FULL_FORBES.replace('[fields.sales]\ntarget = "revenue"', '[fields.sales]\ntarget = "assets"')
    adir = _adapters_with_forbes(tmp_path, wrong)
    fb = E.evaluate(["forbes"], FIX, adir)["per_source"]["forbes"]
    assert fb["schema_f1"] < 1.0
    assert fb["fully_correct_rate"] < 1.0


def test_regression_detection(tmp_path):
    baseline = E.evaluate(["dbpedia"], FIX, SEED_ADAPTERS)
    # Break the dbpedia adapter (drop a required field mapping) → regression.
    broken = SEED_ADAPTERS / "dbpedia.toml"
    text = broken.read_text()
    toml_wo_country = text.replace(
        '[fields.hq_country]\ntarget = "country"\nnormalizer = "country_to_iso"\n\n', ""
    )
    d = tmp_path / "adapters"
    d.mkdir()
    (d / "dbpedia.toml").write_text(toml_wo_country)
    current = E.evaluate(["dbpedia"], FIX, d)
    assert E._detect_regressions(current, baseline) == ["dbpedia"]


def test_regression_detection_skips_none_value_metrics(tmp_path):
    # A source with no gold_records.jsonl (the real-data test split) reports
    # fully_correct_rate=None. Comparing None to a float must not raise, and
    # must not be reported as a regression either direction.
    baseline = {"per_source": {"forbes": {"fully_correct_rate": None}}}
    current = {"per_source": {"forbes": {"fully_correct_rate": 0.5}}}
    assert E._detect_regressions(current, baseline) == []
    baseline2 = {"per_source": {"forbes": {"fully_correct_rate": 0.5}}}
    current2 = {"per_source": {"forbes": {"fully_correct_rate": None}}}
    assert E._detect_regressions(current2, baseline2) == []


def test_evaluate_source_without_gold_records_reports_none(tmp_path):
    # Real-data test split: fixtures dir has target_schema.json, gold_mapping.json,
    # and sources/, but no gold_records.jsonl (no value gold pinned).
    fx = tmp_path / "fixtures"
    (fx / "sources").mkdir(parents=True)
    (fx / "target_schema.json").write_text(
        json.dumps({"attributes": {"name": {"required": True}}})
    )
    (fx / "gold_mapping.json").write_text(json.dumps({"forbes": {"name": "name"}}))
    (fx / "sources" / "forbes.jsonl").write_text(
        json.dumps({"record_id": "1", "name": "Acme"}) + "\n"
    )
    adir = tmp_path / "adapters"
    adir.mkdir()
    (adir / "forbes.toml").write_text(
        'source = "forbes"\n[fields.name]\ntarget = "name"\nnormalizer = "identity"\n'
    )
    res = E.evaluate_source("forbes", fx, adir)
    assert res["value_recall"] is None
    assert res["fully_correct_rate"] is None
    assert res["schema_f1"] == 1.0
    assert res["integrated_rate"] == 1.0


def test_evaluate_source_handles_records_with_no_record_id(tmp_path):
    # Real MaDI-Bench CSVs (unlike the synthetic fixtures) carry no record_id
    # column at all. With no gold_records.jsonl pinned, this must not raise.
    fx = tmp_path / "fixtures"
    (fx / "sources").mkdir(parents=True)
    (fx / "target_schema.json").write_text(
        json.dumps({"attributes": {"name": {"required": True}}})
    )
    (fx / "gold_mapping.json").write_text(json.dumps({"forbes": {"company": "name"}}))
    (fx / "sources" / "forbes.jsonl").write_text(json.dumps({"company": "Acme"}) + "\n")
    adir = tmp_path / "adapters"
    adir.mkdir()
    (adir / "forbes.toml").write_text(
        'source = "forbes"\n[fields.company]\ntarget = "name"\nnormalizer = "identity"\n'
    )
    res = E.evaluate_source("forbes", fx, adir)
    assert res["integrated_rate"] == 1.0
    assert res["value_recall"] is None


def test_full_forbes_toml_is_valid():
    # Guard: the reference "converged" adapter used in tests must parse.
    assert tomllib.loads(FULL_FORBES)["source"] == "forbes"


# --- field_yield: the gold-free signal that a declared mapping actually delivers ---


def _split(tmp_path, source_rows: list[dict], adapter_toml: str, gold: dict) -> tuple[Path, Path]:
    """A self-contained split: sources + schema + mapping gold, no value gold.

    Built here rather than borrowed from fixtures/ so the raw values under test
    are visible in the test itself — these cases turn on the exact value a
    normalizer is handed.
    """
    fx = tmp_path / "fixtures"
    (fx / "sources").mkdir(parents=True)
    (fx / "target_schema.json").write_text(
        json.dumps({"attributes": {"name": {"required": True}, "founded": {}}})
    )
    (fx / "gold_mapping.json").write_text(json.dumps({"fullcontact": gold}))
    (fx / "sources" / "fullcontact.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in source_rows)
    )
    adir = tmp_path / "adapters"
    adir.mkdir()
    (adir / "fullcontact.toml").write_text(adapter_toml)
    return fx, adir


# The shape that shipped on the real fullcontact split: the correspondence
# Attribute_6 -> founded is correct, so schema_f1 rewards it, but the source
# stores full ISO dates and to_int_year parses only a bare year, so not one
# record produces a value.
DEAD_FOUNDED = """source = "fullcontact"
[fields.Attribute_2]
target = "name"
normalizer = "identity"
[fields.Attribute_6]
target = "founded"
normalizer = "to_int_year"
"""

ISO_DATE_ROWS = [
    {"Attribute_2": "BBMG", "Attribute_6": "1908-01-01"},
    {"Attribute_2": "Acme", "Attribute_6": "1955-06-30"},
]


def test_field_yield_exposes_a_mapping_that_schema_f1_calls_perfect(tmp_path):
    fx, adir = _split(
        tmp_path, ISO_DATE_ROWS, DEAD_FOUNDED,
        gold={"Attribute_2": "name", "Attribute_6": "founded"},
    )
    r = E.evaluate_source("fullcontact", fx, adir)
    # Both correspondences are exactly right, so the gold-based metric is perfect.
    assert r["schema_f1"] == 1.0
    # And one of them delivers nothing. This is the gap that let a broken cycle
    # through Gate 2: schema_f1 scores the declaration, field_yield scores the result.
    assert r["field_yield"]["founded"]["rate"] == 0.0
    assert r["field_yield"]["founded"]["produced"] == 0
    assert r["field_yield"]["founded"]["source"] == "Attribute_6"
    assert r["field_yield"]["name"]["rate"] == 1.0
    assert r["field_yield"]["name"]["produced"] == r["records"]


def test_field_yield_is_partial_when_only_some_records_normalize(tmp_path):
    # The real split's `country` case: mostly works, silently fails on empties.
    rows = [
        {"Attribute_2": "BBMG", "Attribute_6": "1908"},
        {"Attribute_2": "Acme", "Attribute_6": ""},
    ]
    fx, adir = _split(tmp_path, rows, DEAD_FOUNDED, gold={"Attribute_6": "founded"})
    r = E.evaluate_source("fullcontact", fx, adir)
    assert r["field_yield"]["founded"] == {
        "source": "Attribute_6", "produced": 1, "records": 2, "rate": 0.5
    }


def test_field_yield_covers_only_declared_mappings(tmp_path):
    fx, adir = _split(tmp_path, ISO_DATE_ROWS, DEAD_FOUNDED, gold={"Attribute_2": "name"})
    r = E.evaluate_source("fullcontact", fx, adir)
    # An unmapped attribute has no yield to report: not claimed yet is a different
    # fact from claimed-and-delivering-nothing, and must not read as 0.0.
    assert set(r["field_yield"]) == {"name", "founded"}
    assert "country" not in r["field_yield"]


def test_field_yield_regression_fires_without_any_gold():
    """The only regression signal that works on the real splits.

    There `fully_correct_rate` is None, so the existing check can never fire and
    a field that used to deliver and now delivers nothing would pass Gate 2
    silently. Yield needs no answer key, so it still catches it.
    """
    def split(founded_rate):
        return {"per_source": {"fullcontact": {
            "fully_correct_rate": None,
            "field_yield": {"founded": {"rate": founded_rate}, "name": {"rate": 1.0}},
        }}}
    assert E._detect_regressions(split(0.0), split(1.0)) == ["fullcontact.founded"]
    assert E._detect_regressions(split(1.0), split(1.0)) == []
    assert E._detect_regressions(split(1.0), split(0.0)) == []


def test_field_yield_regression_ignores_a_newly_added_field():
    # A field absent from the baseline is new work, not a regression.
    baseline = {"per_source": {"fullcontact": {
        "fully_correct_rate": None, "field_yield": {"name": {"rate": 1.0}},
    }}}
    current = {"per_source": {"fullcontact": {
        "fully_correct_rate": None,
        "field_yield": {"name": {"rate": 1.0}, "founded": {"rate": 0.0}},
    }}}
    assert E._detect_regressions(current, baseline) == []


# --- integration ceiling ---------------------------------------------------
# `integrated_rate` alone reads 0.00 both when nobody has mapped the source yet
# and when the source structurally cannot satisfy the schema. That ambiguity used
# to live in prose (Gate 2 asked a human to type "ceiling 0.00" by hand). These
# pin the computed replacement, including the bypass: a source whose gold covers
# every required attribute must NOT be reported as structurally capped.

REQUIRED = ["id", "name", "founded"]


def test_ceiling_is_zero_and_names_what_caps_it_when_gold_covers_no_such_column():
    # The real-split shape: the source has no column gold maps to `founded`.
    records = [{"a": "1", "b": "Acme"}]
    ceiling, unsat = E._integration_ceiling(records, {"a": "id", "b": "name"}, REQUIRED)
    assert ceiling == 0.0
    assert unsat == ["founded"]


def test_ceiling_is_reachable_share_when_every_required_attribute_is_mappable():
    # Two of four records carry a usable value for all three required attributes.
    records = [
        {"a": "1", "b": "Acme", "c": "1998"},
        {"a": "2", "b": "Beta", "c": ""},        # blank founded
        {"a": "3", "b": "Gamma", "c": "null"},   # literal "null" founded
        {"a": "4", "b": "Delta", "c": "2001"},
    ]
    gold = {"a": "id", "b": "name", "c": "founded"}
    ceiling, unsat = E._integration_ceiling(records, gold, REQUIRED)
    assert unsat == []
    assert ceiling == 0.5


def test_ceiling_counts_a_required_attribute_supplied_by_any_of_several_columns():
    records = [{"a": "1", "b": "Acme", "c": "", "d": "1998"}]
    gold = {"a": "id", "b": "name", "c": "founded", "d": "founded"}
    ceiling, unsat = E._integration_ceiling(records, gold, REQUIRED)
    assert unsat == []
    assert ceiling == 1.0  # `d` supplies founded even though `c` is blank


def test_ceiling_of_an_empty_source_is_zero_not_a_division_error():
    # The list is sorted, so it reads the same regardless of schema key order.
    assert E._integration_ceiling([], {"a": "id"}, REQUIRED) == (0.0, ["founded", "name"])


def test_placeholder_detection_matches_the_normalizer_convention():
    for blank in (None, "", "   ", "null", "NULL", "Null"):
        assert E._is_placeholder(blank), blank
    for real in ("0", "Acme", 0, False, "not null"):
        assert not E._is_placeholder(real), real


def test_an_unmapped_but_achievable_source_is_not_reported_as_capped(tmp_path):
    # The distinction the metric exists to make: seed forbes has an empty adapter,
    # so its rate is 0.0 -- but nothing structural stops it reaching 1.0.
    (tmp_path / "forbes.toml").write_text('source = "forbes"\n[fields]\n')
    result = E.evaluate_source("forbes", FIX, tmp_path)
    assert result["integrated_rate"] == 0.0
    assert result["unsatisfiable_required"] == []
    assert result["integrated_ceiling"] > 0.0


def test_a_fully_mapped_source_reaches_its_own_ceiling(tmp_path):
    (tmp_path / "forbes.toml").write_text(FULL_FORBES)
    result = E.evaluate_source("forbes", FIX, tmp_path)
    assert result["integrated_rate"] <= result["integrated_ceiling"]
