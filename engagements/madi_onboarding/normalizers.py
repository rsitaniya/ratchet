"""Named value normalizers referenced by onboarding adapters.

Each normalizer maps a raw source value to a canonical target value, or raises
ValueError when the value can't be normalized (the ingest app records that as an
INVALID_VALUE_FORMAT failure). Adapters are data that reference these by name, so
the loop grows integrations mostly by adding mapping entries — not by writing
code. Only a genuinely new normalizer is a code change.
"""
from __future__ import annotations

import ast
import re

_MAGNITUDES = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}

# Some sources store a founding *date*, not a year (real fullcontact: "1908-01-01").
# to_int_year parses a bare year and cannot be widened without changing what it
# accepts for the sources already pointing at it.
_ISO_DATE = re.compile(r"^(\d{4})-\d{2}-\d{2}$")

# An extensible country-name → ISO 3166-1 alpha-2 table. New entries are a
# one-line data addition (the kind of adapter growth this engagement is about).
# The block below is every distinct country name in the real fullcontact export
# that the seed rows did not already cover.
_COUNTRY_TO_ISO = {
    "united states": "US", "usa": "US", "united states of america": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB",
    "germany": "DE", "india": "IN", "canada": "CA", "france": "FR",
    "japan": "JP", "china": "CN", "australia": "AU", "brazil": "BR",
    "netherlands": "NL", "spain": "ES", "italy": "IT", "sweden": "SE",
    "switzerland": "CH", "ireland": "IE", "belgium": "BE", "austria": "AT",
    "denmark": "DK", "finland": "FI", "norway": "NO", "poland": "PL",
    "portugal": "PT", "greece": "GR", "luxembourg": "LU", "monaco": "MC",
    "ukraine": "UA", "russia": "RU", "serbia": "RS", "croatia": "HR",
    "czech republic": "CZ", "lithuania": "LT", "estonia": "EE", "albania": "AL",
    "bosnia and herzegovina": "BA", "cyprus": "CY", "turkey": "TR", "israel": "IL",
    "iran": "IR", "saudi arabia": "SA", "united arab emirates": "AE", "kuwait": "KW",
    "bahrain": "BH", "oman": "OM", "pakistan": "PK", "bangladesh": "BD",
    "south korea": "KR", "korea, north": "KP", "taiwan": "TW", "hong kong": "HK",
    "singapore": "SG", "malaysia": "MY", "indonesia": "ID", "thailand": "TH",
    "philippines": "PH", "new zealand": "NZ", "mexico": "MX", "argentina": "AR",
    "colombia": "CO", "chile": "CL", "peru": "PE", "bermuda": "BM",
    "greenland": "GL", "south africa": "ZA", "nigeria": "NG", "somalia": "SO",
}
_ISO_CODES = set(_COUNTRY_TO_ISO.values())


def identity(raw):
    """Pass a value through as a string; None is not a valid value."""
    if raw is None:
        raise ValueError("value is missing")
    return str(raw)


def non_empty_text(raw):
    """Pass a value through as a string, rejecting blanks and the literal "null".

    A source that flattens an absent value to "" or to the four characters "null"
    would otherwise have those placeholders counted as produced values, so a field
    that delivered nothing for a quarter of its records would report full yield.
    """
    if raw is None:
        raise ValueError("value is missing")
    s = str(raw)
    if not s.strip() or s.strip().lower() == "null":
        raise ValueError(f"placeholder, not a value: {raw!r}")
    return s


def to_int_year(raw):
    """Parse a 4-digit year to int; reject implausible years."""
    try:
        year = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError(f"not a year: {raw!r}") from None
    if not (1000 <= year <= 2100):
        raise ValueError(f"year out of range: {year}")
    return year


def iso_date_to_year(raw):
    """Take the year out of an ISO-8601 calendar date: "1908-01-01" -> 1908.

    Deliberately strict: a bare year belongs to to_int_year, and accepting both
    here would blur which shape a source actually stores.
    """
    if not isinstance(raw, str):
        raise ValueError(f"not an ISO date: {raw!r}")
    m = _ISO_DATE.match(raw.strip())
    if m is None:
        raise ValueError(f"not an ISO date: {raw!r}")
    return to_int_year(m.group(1))


def currency_to_usd(raw):
    """Parse a currency amount to a float number of USD.

    Accepts plain numbers, and strings like "$1.2B", "$480M", "$5.2K",
    "$1,250,000". Raises ValueError on anything it can't parse.
    """
    if isinstance(raw, int | float) and not isinstance(raw, bool):
        return float(raw)
    if not isinstance(raw, str):
        raise ValueError(f"not a currency value: {raw!r}")
    s = raw.strip().lstrip("$").replace(",", "").strip()
    if not s:
        raise ValueError("empty currency value")
    mult = 1
    if s[-1].upper() in _MAGNITUDES:
        mult = _MAGNITUDES[s[-1].upper()]
        s = s[:-1]
    try:
        return float(s) * mult
    except ValueError:
        raise ValueError(f"not a currency value: {raw!r}") from None


def country_to_iso(raw):
    """Map a country name (or an existing ISO-2 code) to ISO 3166-1 alpha-2."""
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError(f"not a country: {raw!r}")
    s = raw.strip()
    if len(s) == 2 and s.upper() in _ISO_CODES:
        return s.upper()
    try:
        return _COUNTRY_TO_ISO[s.lower()]
    except KeyError:
        raise ValueError(f"unknown country: {raw!r}") from None


def to_list(raw):
    """Wrap a scalar in a single-element list; pass a list through."""
    if isinstance(raw, list):
        return raw
    if raw is None:
        raise ValueError("value is missing")
    return [raw]


def to_text_list(raw):
    """Normalize a text column holding one value or many into a list of strings.

    Real fullcontact Attribute_5 has exactly three shapes across its 1931 records:
    "" (1739), a bare name like "Raphael Bemporad" (120), and a *stringified* Python
    list literal like "['Ron Wayne', 'Steve Jobs', 'Steve Wozniak']" (72) — a string
    whose content is a list, not a JSON array. to_list fits none of them: it turns ""
    into [""] and the literal into one element holding the raw text, so a column that
    delivers key people for a tenth of its records would report full yield.

    A bracketed value that does not parse raises rather than degrading to a
    one-element list, so a shape nobody anticipated surfaces as INVALID_VALUE_FORMAT
    instead of as a plausible wrong value.
    """
    s = non_empty_text(raw).strip()
    if not s.startswith("["):
        return [s]
    try:
        items = ast.literal_eval(s)
    except (ValueError, SyntaxError, TypeError):
        raise ValueError(f"not a list literal: {raw!r}") from None
    if not isinstance(items, list):
        raise ValueError(f"not a list literal: {raw!r}")
    values = [str(v).strip() for v in items if str(v).strip()]
    if not values:
        raise ValueError(f"list literal holds no values: {raw!r}")
    return values


_REGISTRY = {
    "identity": identity,
    "non_empty_text": non_empty_text,
    "to_int_year": to_int_year,
    "iso_date_to_year": iso_date_to_year,
    "currency_to_usd": currency_to_usd,
    "country_to_iso": country_to_iso,
    "to_list": to_list,
    "to_text_list": to_text_list,
}


def get(name: str):
    """Return the normalizer registered under `name`, or raise KeyError."""
    return _REGISTRY[name]
