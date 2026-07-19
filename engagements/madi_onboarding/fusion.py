"""Pure data-fusion engine: consolidate a matched cluster into one record.

Given a cluster of (source, record) pairs for the same entity and declarative
fusion rules (a per-attribute conflict-resolution strategy), produce one fused
record. Rules are data the loop grows; this engine is code the loop is forbidden
to edit. A better fused record = higher fusion accuracy vs the gold fused records.
"""
from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

RULES_PATH = Path(__file__).resolve().parent / "fusion_rules.toml"


def load_rules(path: Path | None = None) -> dict[str, Any]:
    """Load fusion rules; a missing file means 'take the first source for everything'."""
    path = path or RULES_PATH
    if not path.exists():
        return {"default_strategy": "first", "source_priority": [], "attributes": {}}
    return tomllib.loads(path.read_text())


def _ranked(cluster: list[dict], order: list[str]) -> list[dict]:
    def rank(cr):
        return order.index(cr["source"]) if cr["source"] in order else len(order)
    return sorted(cluster, key=rank)


def _apply(strategy: str, cluster: list[dict], attr: str, order: list[str]):
    values = [(cr["source"], cr["record"].get(attr)) for cr in cluster]
    non_null = [(s, v) for s, v in values if v is not None]
    if not non_null:
        return None
    if strategy in ("prefer_source", "first"):
        ranked = _ranked([cr for cr in cluster if cr["record"].get(attr) is not None], order) \
            if strategy == "prefer_source" else [cr for cr in cluster if cr["record"].get(attr) is not None]
        return ranked[0]["record"].get(attr)
    if strategy == "longest":
        return max((v for _, v in non_null), key=lambda v: len(str(v)))
    if strategy == "max":
        return max(v for _, v in non_null)
    if strategy == "min":
        return min(v for _, v in non_null)
    if strategy == "union":
        out: list = []
        for _, v in non_null:
            for item in (v if isinstance(v, list) else [v]):
                if item not in out:
                    out.append(item)
        return out
    raise ValueError(f"unknown fusion strategy: {strategy!r}")


def fuse(cluster: list[dict], rules: dict, target_attrs: list[str]) -> dict:
    """Fuse a cluster of {"source", "record"} into one record over target_attrs."""
    default = rules.get("default_strategy", "prefer_source")
    global_order = rules.get("source_priority", [])
    attr_rules = rules.get("attributes", {})
    fused: dict[str, Any] = {}
    for attr in target_attrs:
        ar = attr_rules.get(attr, {})
        strategy = ar.get("strategy", default)
        order = ar.get("source_priority", global_order)
        fused[attr] = _apply(strategy, cluster, attr, order)
    return fused
