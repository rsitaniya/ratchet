"""Named value normalizers referenced by onboarding adapters.

Each normalizer maps a raw source value to a canonical target value, or raises
ValueError when the value can't be normalized (the ingest app records that as an
INVALID_VALUE_FORMAT failure). Adapters are data that reference these by name, so
the loop grows integrations mostly by adding mapping entries — not by writing
code. Only a genuinely new normalizer is a code change.
"""
from __future__ import annotations

_MAGNITUDES = {"K": 1_000, "M": 1_000_000, "B": 1_000_000_000, "T": 1_000_000_000_000}

# A small, extensible country-name → ISO 3166-1 alpha-2 table. New entries are a
# one-line data addition (the kind of adapter growth this engagement is about).
_COUNTRY_TO_ISO = {
    "united states": "US", "usa": "US", "united states of america": "US",
    "united kingdom": "GB", "uk": "GB", "great britain": "GB",
    "germany": "DE", "india": "IN", "canada": "CA", "france": "FR",
    "japan": "JP", "china": "CN", "australia": "AU", "brazil": "BR",
    "netherlands": "NL", "spain": "ES", "italy": "IT", "sweden": "SE",
    # Every remaining country name that occurs on the real fullcontact split.
    "ireland": "IE", "switzerland": "CH", "hong kong": "HK", "taiwan": "TW",
    "united arab emirates": "AE", "saudi arabia": "SA", "greece": "GR",
    "turkey": "TR", "austria": "AT", "mexico": "MX", "south africa": "ZA",
    "singapore": "SG", "argentina": "AR", "denmark": "DK", "israel": "IL",
    "belgium": "BE", "indonesia": "ID", "colombia": "CO", "nigeria": "NG",
    "finland": "FI", "russia": "RU", "malaysia": "MY", "norway": "NO",
    "thailand": "TH", "south korea": "KR", "korea, north": "KP",
    "bermuda": "BM", "philippines": "PH", "luxembourg": "LU", "portugal": "PT",
    "pakistan": "PK", "kuwait": "KW", "greenland": "GL", "ukraine": "UA",
    "serbia": "RS", "bangladesh": "BD", "croatia": "HR", "somalia": "SO",
    "iran": "IR", "cyprus": "CY", "new zealand": "NZ", "chile": "CL",
    "lithuania": "LT", "poland": "PL", "estonia": "EE", "albania": "AL",
    "peru": "PE", "monaco": "MC", "czech republic": "CZ", "oman": "OM",
    "bosnia and herzegovina": "BA", "bahrain": "BH",
}
_ISO_CODES = set(_COUNTRY_TO_ISO.values())


def identity(raw):
    """Pass a value through as a string; None is not a valid value."""
    if raw is None:
        raise ValueError("value is missing")
    return str(raw)


def non_placeholder_str(raw):
    """Pass a string through, rejecting a source's stand-ins for "no value".

    Some sources write an empty string, or the literal text "null", where they
    simply have nothing. identity() would emit those as if they were real values,
    so a column that uses them needs this instead.
    """
    if raw is None:
        raise ValueError("value is missing")
    s = str(raw).strip()
    if not s or s.lower() == "null":
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
    """Take the year out of an ISO calendar date: "1908-01-01" -> 1908.

    A source that stores a founding *date* rather than a year needs this;
    to_int_year parses a bare year and rejects the full date shape.
    """
    if not isinstance(raw, str):
        raise ValueError(f"not an ISO date: {raw!r}")
    head = raw.strip().split("-", 1)[0]
    if len(head) != 4:
        raise ValueError(f"not an ISO date: {raw!r}")
    return to_int_year(head)


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


_REGISTRY = {
    "identity": identity,
    "non_placeholder_str": non_placeholder_str,
    "to_int_year": to_int_year,
    "iso_date_to_year": iso_date_to_year,
    "currency_to_usd": currency_to_usd,
    "country_to_iso": country_to_iso,
    "to_list": to_list,
}


def get(name: str):
    """Return the normalizer registered under `name`, or raise KeyError."""
    return _REGISTRY[name]
