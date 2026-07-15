"""Loads flywheel.toml — the seam between the generic loop and one specific API.

Both the simulator and the usage analyzer read their domain knowledge from here
rather than hardcoding it, so pointing the flywheel at a different FastAPI app is
a config edit rather than a code edit. See docs/ADAPTING.md.

Every value has a working default: a missing flywheel.toml is not an error.
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "flywheel.toml"

DEFAULTS: dict[str, dict[str, Any]] = {
    "app": {
        "module": "app.main:app",
        "base_url": "http://localhost:8000",
        "version_files": [],
    },
    "simulator": {
        "edge_cases": "edge_cases.json",
        "default_requests": 30,
    },
    "signals": {
        "numeric_params": [],
        "zero_value_params": [],
    },
}


def load_config(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Return config merged over DEFAULTS, section by section."""
    path = path or CONFIG_PATH
    raw: dict[str, Any] = {}
    if path.exists():
        raw = tomllib.loads(path.read_text())
    return {section: {**defaults, **raw.get(section, {})} for section, defaults in DEFAULTS.items()}


def load_edge_cases(config: dict[str, dict[str, Any]] | None = None) -> dict[str, list[dict]]:
    """Return the correlated edge-case overlay, or {} if none is configured.

    An absent or empty overlay is a supported mode, not a failure: the simulator
    still exercises every endpoint using values synthesized from the schema alone.
    Keys beginning with "_" are documentation and are dropped.
    """
    config = config or load_config()
    rel = config["simulator"].get("edge_cases")
    if not rel:
        return {}
    path = REPO_ROOT / rel
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, list)}
