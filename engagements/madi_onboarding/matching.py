"""Pure entity-matching engine: decide which records refer to the same entity.

Given two schema-mapped record sets and declarative matching rules (a blocking
key, a set of weighted field comparisons, and a threshold), produce predicted
matched pairs. The rules are data the loop grows; this engine is code the loop is
forbidden to edit. Onboarding a matcher = raising its F1 vs gold labeled pairs by
improving the rules (better similarity, useful blocking, tuned threshold).
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from . import similarity

RULES_PATH = Path(__file__).resolve().parent / "matching_rules.toml"


def load_rules(path: Path | None = None) -> dict[str, Any]:
    """Load matching rules; a missing file means 'no matcher yet' (matches nothing)."""
    path = path or RULES_PATH
    if not path.exists():
        return {"threshold": 1.0, "compare": []}
    rules = tomllib.loads(path.read_text())
    for c in rules.get("compare", []):
        if "field" not in c or "similarity" not in c:
            raise ValueError(f"matching rule needs 'field' and 'similarity': {c}")
        similarity.get(c["similarity"])  # validate the name exists
    return rules


def score_pair(left: dict, right: dict, compares: list[dict]) -> float:
    """Weighted average of per-field similarities in [0, 1]."""
    total_w = sum(c.get("weight", 1.0) for c in compares)
    if not total_w:
        return 0.0
    score = 0.0
    for c in compares:
        fn = similarity.get(c["similarity"])
        score += c.get("weight", 1.0) * fn(left.get(c["field"]), right.get(c["field"]))
    return score / total_w


def match(left: list[dict], right: list[dict], rules: dict) -> list[tuple[str, str]]:
    """Return predicted (left_id, right_id) matched pairs, each side used at most once.

    A blocking key (optional) skips comparing records that disagree on it — the
    standard candidate-reduction step. Every pair scoring >= threshold is a
    candidate; candidates are then assigned greedily by descending score, so a
    record already claimed by a higher-scoring pair can never also be handed to
    a second match on the other side (an entity is one entity).
    """
    for rec in (*left, *right):
        if similarity.is_absent(rec.get("record_id")):
            raise ValueError(f"record missing required 'record_id': {rec}")
    threshold = rules.get("threshold", 0.85)
    blocking = rules.get("blocking_key")
    compares = rules.get("compare", [])
    candidates: list[tuple[float, str, str]] = []
    for lrec in left:
        for rrec in right:
            if blocking:
                lb, rb = lrec.get(blocking), rrec.get(blocking)
                # An absent blocking key is not a shared block: two records that
                # both lack it must not be grouped together (that is how missing
                # fields produced false matches).
                if similarity.is_absent(lb) or similarity.is_absent(rb) or lb != rb:
                    continue
            score = score_pair(lrec, rrec, compares)
            if score >= threshold:
                candidates.append((score, lrec["record_id"], rrec["record_id"]))

    candidates.sort(key=lambda c: c[0], reverse=True)
    matched_left: set[str] = set()
    matched_right: set[str] = set()
    pairs: list[tuple[str, str]] = []
    for _score, lid, rid in candidates:
        if lid in matched_left or rid in matched_right:
            continue
        matched_left.add(lid)
        matched_right.add(rid)
        pairs.append((lid, rid))
    return pairs
