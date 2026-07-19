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
}
_ISO_CODES = set(_COUNTRY_TO_ISO.values())


def identity(raw):
    """Pass a value through as a string; None is not a valid value."""
    if raw is None:
        raise ValueError("value is missing")
    return str(raw)


def to_int_year(raw):
    """Parse a 4-digit year to int; reject implausible years."""
    try:
        year = int(str(raw).strip())
    except (TypeError, ValueError):
        raise ValueError(f"not a year: {raw!r}") from None
    if not (1000 <= year <= 2100):
        raise ValueError(f"year out of range: {year}")
    return year


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
    "to_int_year": to_int_year,
    "currency_to_usd": currency_to_usd,
    "country_to_iso": country_to_iso,
    "to_list": to_list,
}


def get(name: str):
    """Return the normalizer registered under `name`, or raise KeyError."""
    return _REGISTRY[name]
