"""Named similarity functions referenced by entity-matching rules.

Each returns a score in [0, 1] for a pair of values. Matching rules are data that
reference these by name (like normalizers), so the loop grows a matcher mostly by
adding/weighting comparisons — not by writing code.
"""
from __future__ import annotations


def is_absent(v) -> bool:
    """A value carrying no evidence: None or an empty/whitespace string.

    Two records that both *lack* a field must not be treated as matching on it,
    so every similarity returns 0.0 when either side is absent.
    """
    return v is None or (isinstance(v, str) and not v.strip())


def exact(a, b) -> float:
    if is_absent(a) or is_absent(b):
        return 0.0
    return 1.0 if a == b else 0.0


def _jaro(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0
    max_dist = max(len1, len2) // 2 - 1
    match1 = [False] * len1
    match2 = [False] * len2
    matches = 0
    for i in range(len1):
        start = max(0, i - max_dist)
        end = min(i + max_dist + 1, len2)
        for j in range(start, end):
            if not match2[j] and s1[i] == s2[j]:
                match1[i] = match2[j] = True
                matches += 1
                break
    if matches == 0:
        return 0.0
    # transpositions
    t = 0
    k = 0
    for i in range(len1):
        if match1[i]:
            while not match2[k]:
                k += 1
            if s1[i] != s2[k]:
                t += 1
            k += 1
    t //= 2
    return (matches / len1 + matches / len2 + (matches - t) / matches) / 3.0


def jaro_winkler(a, b, prefix_weight: float = 0.1) -> float:
    """Jaro-Winkler similarity (case-insensitive), boosting a common prefix."""
    if is_absent(a) or is_absent(b):
        return 0.0
    s1, s2 = str(a).lower(), str(b).lower()
    jaro = _jaro(s1, s2)
    prefix = 0
    for c1, c2 in zip(s1, s2, strict=False):
        if c1 == c2:
            prefix += 1
        else:
            break
        if prefix == 4:
            break
    return jaro + prefix * prefix_weight * (1 - jaro)


def token_jaccard(a, b) -> float:
    """Jaccard overlap of lowercased token sets."""
    if is_absent(a) or is_absent(b):
        return 0.0
    t1 = set(str(a).lower().split())
    t2 = set(str(b).lower().split())
    if not t1 and not t2:
        return 1.0
    union = t1 | t2
    return len(t1 & t2) / len(union) if union else 1.0


def numeric_close(a, b, rel_tol: float = 0.05) -> float:
    """1.0 if two numbers are within `rel_tol` relative tolerance, else 0.0."""
    if is_absent(a) or is_absent(b):
        return 0.0
    try:
        x, y = float(a), float(b)
    except (TypeError, ValueError):
        return 0.0
    if x == y:
        return 1.0
    scale = max(abs(x), abs(y))
    return 1.0 if scale and abs(x - y) / scale <= rel_tol else 0.0


_REGISTRY = {
    "exact": exact,
    "jaro_winkler": jaro_winkler,
    "token_jaccard": token_jaccard,
    "numeric_close": numeric_close,
}


def get(name: str):
    return _REGISTRY[name]
