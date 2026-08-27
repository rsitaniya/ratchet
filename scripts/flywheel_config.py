"""Loads flywheel.toml — the seam between the generic loop and one specific API.

The simulator reads its domain knowledge from here rather than hardcoding it, so
pointing the flywheel at a different FastAPI app is a config edit rather than a
code edit. See docs/ADAPTING.md. `[app].analyzer` is required, not optional:
there is no generic fallback analyzer — an engagement's telemetry shape is its
own, so its gap-ranker is too.

Which config file is active is chosen by (in order): an explicit path argument,
the FLYWHEEL_CONFIG environment variable, then the repo-root flywheel.toml. This
lets more than one app (e.g. engagements under engagements/) run its own loop
without disturbing another's. Path-valued keys are resolved against the
config file's own directory, so an engagement config refers to its own files.

A missing config is not an error when it is *implicit* (no path argument, no
FLYWHEEL_CONFIG set — the repo-root default, which no longer exists since the
calculator example was removed): every value has a working default, and tools
like the simulator legitimately run with no app selected. An *explicit*
FLYWHEEL_CONFIG that names a file that does not exist is different: it is an
operator typo, and silently falling back to defaults there would mean a
security-relevant key like [protected].paths goes from "the intended engagement's
list" to "empty" with no signal. config_path() raises for that case only.

As a CLI, prints one value so shell steps can stay generic:
    python scripts/flywheel_config.py --get app.module
"""
from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = REPO_ROOT / "flywheel.toml"

DEFAULTS: dict[str, dict[str, Any]] = {
    "app": {
        "module": "myservice.api:app",
        "base_url": "http://localhost:8000",
        "usage_log": "usage_log.jsonl",
        # Per-cycle delivery telemetry (see scripts/cycle_log.py) — what each
        # cycle cost in wall-clock, human gate time, and retries. Committed
        # evidence, same as the run receipts beside it.
        "cycle_log": "runs/delivery/cycles.jsonl",
        # Optional overrides for the app's target schema / adapters directory —
        # empty means "use the app's own hardcoded default." Only a config that
        # points the app at a different dataset (e.g. the real-data test split)
        # needs to set these.
        "target_schema": "",
        "adapters_dir": "",
        # Optional command the dev-loop runs at Gate 2 to score a proposed patch
        # against held-out truth. Empty for apps without an evaluator.
        "evaluator": "",
        # Required command the dev-loop runs to turn the usage log into the
        # signal report STEP 2 proposes from. Empty here only because DEFAULTS
        # supports apps with no config file at all (see config_path()) — every
        # engagement that wants /dev-loop to run STEP 2 must set this. A
        # command, not a path, so it is not resolved.
        "analyzer": "",
    },
    "simulator": {
        "default_requests": 30,
    },
    "traffic": {
        "replay_file": "",
    },
    # Two different boundaries, deliberately separate lists.
    #
    # `paths`   — globs the implementer may never WRITE (held-out evaluators,
    #             gold labels, fixtures, scoring). check_protected_paths.py
    #             rejects a submission touching one.
    # `unreadable` — globs the implementer may never READ. Strictly narrower in
    #             intent: it needs to read the engines and app source it edits
    #             against, but must never see an answer key or a prior cycle's
    #             converged output. check_readable.py enforces it as a
    #             PreToolUse hook scoped to that one subagent.
    #
    # Unwritable is not the same set as unreadable, so unifying them would
    # either blind the implementer to code it must read or leave gold readable.
    "protected": {
        "paths": [],
        "unreadable": [],
    },
}

# Config keys whose values are filesystem paths. They are resolved relative to
# the config file's own directory so an engagement config in a subdirectory
# refers to its own files, not the repo root's. Non-path keys (module, base_url)
# are deliberately excluded — resolving them would corrupt import paths and URLs.
PATH_KEYS: dict[str, tuple[str, ...]] = {
    "app": ("usage_log", "cycle_log", "target_schema", "adapters_dir"),
    "traffic": ("replay_file",),
}


def config_path(path: Path | str | None = None) -> Path:
    """Resolve which config file to load: explicit arg > $FLYWHEEL_CONFIG > default.

    Raises FileNotFoundError only when $FLYWHEEL_CONFIG is set and does not
    exist — an operator typo, not a supported "no app selected" state. An
    explicit `path` argument and the repo-root default both stay permissive:
    a caller that resolved its own path (or the implicit default when no
    config was named at all) is a mode this loader has always supported, and
    load_config() already handles a nonexistent path there by returning
    defaults.
    """
    if path is not None:
        return Path(path)
    env = os.environ.get("FLYWHEEL_CONFIG")
    if not env:
        return DEFAULT_CONFIG_PATH
    env_path = Path(env)
    if not env_path.exists():
        raise FileNotFoundError(
            f"FLYWHEEL_CONFIG={env!r} does not exist. Fix the path, or unset "
            f"FLYWHEEL_CONFIG to fall back to {DEFAULT_CONFIG_PATH}."
        )
    return env_path


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
    except FileNotFoundError as e:
        raise SystemExit(str(e)) from None
    if isinstance(val, list):
        print(" ".join(map(str, val)))
    else:
        print(val)


if __name__ == "__main__":
    main()
