"""Tests for the protected held-out evaluator (the semantic oracle)."""
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
    assert fb["value_accuracy"] == 1.0
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


def test_full_forbes_toml_is_valid():
    # Guard: the reference "converged" adapter used in tests must parse.
    assert tomllib.loads(FULL_FORBES)["source"] == "forbes"
