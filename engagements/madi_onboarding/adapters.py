"""Load declarative source adapters and apply them to raw records.

An adapter is data (a TOML file): for one source system it maps each source
field to a target attribute plus a named normalizer. Onboarding a new source =
growing its adapter. The mapping engine here is pure and framework-free so it can
be unit-tested without a server; the ingest app is a thin wrapper over it.
"""
from __future__ import annotations

import re
import tomllib
from pathlib import Path
from typing import Any

from . import normalizers

ADAPTERS_DIR = Path(__file__).resolve().parent / "adapters"

# A source system names a file under adapters/. Restrict it to a safe token so a
# caller-supplied value cannot traverse the filesystem (e.g. "../../etc/passwd").
SAFE_SOURCE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")


def load_adapter(source: str, adapters_dir: Path | None = None) -> dict[str, Any]:
    """Load and validate one source adapter.

    A missing adapter is a supported state (a not-yet-onboarded source): it
    returns an empty field map, so every field is unmapped and every required
    target attribute is missing — which is exactly the signal the loop acts on.
    Referencing an unknown normalizer is an authoring error and raises loudly.
    An unsafe source name is rejected before it can become a path.
    """
    adapters_dir = adapters_dir or ADAPTERS_DIR
    if not isinstance(source, str) or not SAFE_SOURCE.match(source):
        raise ValueError(f"invalid source system name: {source!r}")
    path = adapters_dir / f"{source}.toml"
    # Defense in depth: the resolved path must stay under adapters_dir.
    if adapters_dir.resolve() not in path.resolve().parents:
        raise ValueError(f"adapter path escapes adapters dir: {source!r}")
    if not path.exists():
        return {"source": source, "fields": {}}
    data = tomllib.loads(path.read_text())
    fields = data.get("fields", {})
    for src_field, spec in fields.items():
        if "target" not in spec or "normalizer" not in spec:
            raise ValueError(f"adapter {source}: field {src_field!r} needs 'target' and 'normalizer'")
        try:
            normalizers.get(spec["normalizer"])
        except KeyError:
            raise ValueError(
                f"adapter {source}: field {src_field!r} references unknown normalizer {spec['normalizer']!r}"
            ) from None
    return {"source": source, "fields": fields}


def apply_adapter(record: dict, adapter: dict, target_schema: dict) -> dict:
    """Map + normalize one raw record. Pure.

    Returns {target, failures, integrated}. `failures` is a list of
    {stage, error_code, field}. A record is `integrated` only when it produces
    every required target attribute with no failures.
    """
    fields = adapter.get("fields", {})
    target: dict[str, Any] = {}
    failures: list[dict] = []
    attempted_targets: set[str] = set()

    for src_field, raw in record.items():
        if src_field == "record_id":
            continue
        mapping = fields.get(src_field)
        if not mapping:
            failures.append({"stage": "schema_matching", "error_code": "UNMAPPED_FIELD", "field": src_field})
            continue
        attempted_targets.add(mapping["target"])
        normalizer = normalizers.get(mapping["normalizer"])
        try:
            target[mapping["target"]] = normalizer(raw)
        except ValueError:
            failures.append(
                {"stage": "value_normalization", "error_code": "INVALID_VALUE_FORMAT", "field": src_field}
            )

    required = [a for a, s in target_schema.get("attributes", {}).items() if s.get("required")]
    for attr in required:
        if attr not in target and attr not in attempted_targets:
            # Only flag truly-unmapped required attrs; a mapped-but-unnormalized
            # one is already reported as INVALID_VALUE_FORMAT above.
            failures.append({"stage": "schema_matching", "error_code": "MISSING_REQUIRED_FIELD", "field": attr})

    # A record is integrated when every REQUIRED target attribute was produced.
    # Unmapped OPTIONAL fields remain as failures (coverage signal the loop acts
    # on) but do not block integration — the record is already usable.
    integrated = all(attr in target for attr in required)
    return {"target": target, "failures": failures, "integrated": integrated}
