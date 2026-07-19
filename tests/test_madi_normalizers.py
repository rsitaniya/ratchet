"""Unit tests for the value normalizers the onboarding adapters reference.

Normalizers turn a raw source value into a canonical target value, or raise
ValueError (which the ingest app records as INVALID_VALUE_FORMAT). They are the
reusable, named library; adapters are data that point at them by name.
"""
import pytest

from engagements.madi_onboarding import normalizers as n


def test_registry_lookup():
    assert n.get("to_int_year") is n.to_int_year
    with pytest.raises(KeyError):
        n.get("does_not_exist")


@pytest.mark.parametrize("raw,expected", [("2009", 2009), (1987, 1987), (" 2001 ", 2001)])
def test_to_int_year_ok(raw, expected):
    assert n.to_int_year(raw) == expected


@pytest.mark.parametrize("raw", ["not-a-year", "", "99", "3200"])
def test_to_int_year_bad(raw):
    with pytest.raises(ValueError):
        n.to_int_year(raw)


@pytest.mark.parametrize("raw,expected", [
    ("$1.2B", 1_200_000_000.0),
    ("$480M", 480_000_000.0),
    ("$5.2K", 5_200.0),
    ("$2.1B", 2_100_000_000.0),
    ("1200000", 1_200_000.0),
    (890000000, 890_000_000.0),
    ("$1,250,000", 1_250_000.0),
])
def test_currency_to_usd_ok(raw, expected):
    assert n.currency_to_usd(raw) == expected


@pytest.mark.parametrize("raw", ["cheap", "", "$$", None])
def test_currency_to_usd_bad(raw):
    with pytest.raises(ValueError):
        n.currency_to_usd(raw)


@pytest.mark.parametrize("raw,expected", [
    ("United States", "US"),
    ("united kingdom", "GB"),
    ("Germany", "DE"),
    ("India", "IN"),
    ("Canada", "CA"),
    ("US", "US"),
    ("de", "DE"),
])
def test_country_to_iso_ok(raw, expected):
    assert n.country_to_iso(raw) == expected


@pytest.mark.parametrize("raw", ["Atlantis", "", "XYZ", None])
def test_country_to_iso_bad(raw):
    with pytest.raises(ValueError):
        n.country_to_iso(raw)


def test_identity_and_to_list():
    assert n.identity("Acme") == "Acme"
    with pytest.raises(ValueError):
        n.identity(None)
    assert n.to_list("Dana Reyes") == ["Dana Reyes"]
    assert n.to_list(["A", "B"]) == ["A", "B"]
