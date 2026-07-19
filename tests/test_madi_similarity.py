"""Tests for the named similarity functions used by matching rules."""
import pytest

from engagements.madi_onboarding import similarity as S


def test_registry():
    assert S.get("jaro_winkler") is S.jaro_winkler
    with pytest.raises(KeyError):
        S.get("nope")


def test_exact():
    assert S.exact("US", "US") == 1.0
    assert S.exact("US", "GB") == 0.0


def test_jaro_winkler_known_value():
    # Canonical reference pair from the Jaro-Winkler literature.
    assert S.jaro_winkler("MARTHA", "MARHTA") == pytest.approx(0.961, abs=0.002)
    assert S.jaro_winkler("", "") == 1.0
    assert S.jaro_winkler("abc", "") == 0.0


def test_jaro_winkler_name_variants_are_high():
    # The kind of fuzzy match the loop must learn to accept.
    assert S.jaro_winkler("nimbus robotics", "nimbus robotics, inc.") > 0.9
    assert S.jaro_winkler("vantage logistics", "vantage logistics ltd") > 0.9


def test_jaro_winkler_distinct_names_are_low():
    # Distinct company names must score well below the ~0.9 match threshold,
    # so a matcher using this similarity separates true pairs from distractors.
    assert S.jaro_winkler("cobalt systems", "solaris textiles") < 0.75


def test_token_jaccard():
    assert S.token_jaccard("Nimbus Robotics", "Nimbus Robotics Inc") == pytest.approx(2 / 3, abs=0.01)
    assert S.token_jaccard("a b", "a b") == 1.0
    assert S.token_jaccard("", "") == 1.0


def test_numeric_close():
    assert S.numeric_close(1_000_000, 1_020_000) == 1.0   # within 5%
    assert S.numeric_close(1_000_000, 1_500_000) == 0.0   # far apart
    assert S.numeric_close(0, 0) == 1.0
    assert S.numeric_close("x", 5) == 0.0                 # non-numeric → 0
