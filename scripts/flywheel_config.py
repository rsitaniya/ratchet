"""Loads flywheel.toml — the seam between the generic loop and one specific API.

Both the simulator and the usage analyzer read their domain knowledge from here
rather than hardcoding it, so pointing the flywheel at a different FastAPI app is
a config edit rather than a code edit. See docs/ADAPTING.md.

Which config file is active is chosen by (in order): an explicit path argument,
the FLYWHEEL_CONFIG environment variable, then the repo-root flywheel.toml. This
lets a second app (e.g. an engagement under engagements/) run its own loop
without disturbing the calculator's. Path-valued keys are resolved against the
config file's own directory, so an engagement config refers to its own files.

Every value has a working default: a missing flywheel.toml is not an error.

As a CLI, prints one value so shell steps can stay generic:
    python scripts/flywheel_config.py --get app.module
"""
from __future__ import annotations

import json
import os
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "flywheel.toml"

DEFAULTS: dict[str, dict[str, Any]] = {
    "app": {
        "module": "app.main:app",
        "base_url": "http://localhost:8000",
        "usage_log": "usage_log.jsonl",
        "version_files": [],
        # Optional command the dev-loop runs at Gate 2 to score a proposed patch
        # against held-out truth. Empty for apps without an evaluator.
        "evaluator": "",
        # Optional analyzer command the dev-loop runs to turn the usage log into
        # the signal report the feature-suggester reads. Empty → the generic HTTP
        # analyzer (scripts/analyze_usage.py); an engagement points it at its own
        # domain gap-ranker. A command, not a path, so it is not resolved.
        "analyzer": "",
    },
    "simulator": {
        "edge_cases": "edge_cases.json",
        "default_requests": 30,
    },
    "signals": {
        "numeric_params": [],
        "zero_value_params": [],
    },
    "traffic": {
        "replay_file": "",
    },
    # Glob patterns the implementer patch may never touch (held-out evaluators,
    # gold labels, fixtures, scoring). The orchestrator rejects patches that do.
    "protected": {
        "paths": [],
    },
}

# Config keys whose values are filesystem paths. They are resolved relative to
# the config file's own directory so an engagement config in a subdirectory
# refers to its own files, not the repo root's. Non-path keys (module, base_url)
# are deliberately excluded — resolving them would corrupt import paths and URLs.
PATH_KEYS: dict[str, tuple[str, ...]] = {
    "app": ("usage_log",),
    "simulator": ("edge_cases",),
    "traffic": ("replay_file",),
}


def config_path(path: Path | str | None = None) -> Path:
    """Resolve which config file to load: explicit arg > $FLYWHEEL_CONFIG > default."""
    if path is not None:
        return Path(path)
    env = os.environ.get("FLYWHEEL_CONFIG")
    return Path(env) if env else DEFAULT_CONFIG_PATH


def load_config(path: Path | str | None = None) -> dict[str, dict[str, Any]]:
    """Return config merged over DEFAULTS, with path-valued keys made absolute.

    Sections present in the file but absent from DEFAULTS are preserved, so a
    new section like [traffic] is never silently dropped. Path-valued keys named
    in PATH_KEYS are resolved against the config file's directory.
    """
    cfg_path = config_path(path)
    raw: dict[str, Any] = {}
    if cfg_path.exists():
        raw = tomllib.loads(cfg_path.read_text())

    merged: dict[str, dict[str, Any]] = {}
    for section in set(DEFAULTS) | set(raw):
        section_raw = raw.get(section, {})
        if isinstance(section_raw, dict):
            merged[section] = {**DEFAULTS.get(section, {}), **section_raw}
        else:
            merged[section] = section_raw

    base = cfg_path.resolve().parent
    for section, keys in PATH_KEYS.items():
        sect = merged.get(section)
        if not isinstance(sect, dict):
            continue
        for key in keys:
            val = sect.get(key)
            if val:  # non-empty string only; "" stays "" (means "unset")
                sect[key] = str((base / val).resolve())
    return merged


def load_edge_cases(config: dict[str, dict[str, Any]] | None = None) -> dict[str, list[dict]]:
    """Return the correlated edge-case overlay, or {} if none is configured.

    An absent or empty overlay is a supported mode, not a failure: the simulator
    still exercises every endpoint using values synthesized from the schema alone.
    Keys beginning with "_" are documentation and are dropped.
    """
    config = config or load_config()
    path_str = config["simulator"].get("edge_cases")
    if not path_str:
        return {}
    path = Path(path_str)  # already resolved to absolute by load_config
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return {k: v for k, v in data.items() if not k.startswith("_") and isinstance(v, list)}


def get_value(dotted: str, config: dict[str, dict[str, Any]] | None = None) -> Any:
    """Return one config value named as SECTION.KEY (e.g. "app.module")."""
    section, _, key = dotted.partition(".")
    if not key:
        raise KeyError(f"expected SECTION.KEY, got: {dotted!r}")
    config = config or load_config()
    return config[section][key]


def main(argv: list[str] | None = None) -> None:
    import argparse

    ap = argparse.ArgumentParser(description="Print one value from the active flywheel.toml")
    ap.add_argument("--get", metavar="SECTION.KEY", required=True, help="e.g. app.module")
    args = ap.parse_args(argv)
    try:
        val = get_value(args.get)
    except KeyError:
        raise SystemExit(f"no such config key: {args.get!r}") from None
    if isinstance(val, list):
        print(" ".join(map(str, val)))
    else:
        print(val)


if __name__ == "__main__":
    main()
