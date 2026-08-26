#!/usr/bin/env python3
"""
Schema-driven, multi-endpoint API simulator — with an optional replay mode.

Default (schema) mode: fetches /openapi.json and exercises every operation it
finds — each path + method — by synthesizing requests from the parameter schemas
(path- and operation-level, `$ref` resolved) and application/json request bodies.
It is generic by construction: a new endpoint is exercised automatically with no
hand-editing, as long as it is described in /openapi.json. Non-JSON request media
types are not synthesized.

Replay mode (`--replay FILE`, or `[traffic].replay_file` in flywheel.toml): fires
a fixed list of recorded request specs instead of synthesizing them, so a run is
reproducible. Each line of the replay file is one spec:

    {"method": "POST", "path": "/requests/mortgage", "query": {}, "body": {...},
     "meta": {"record_id": "...", "category": "..."}}

`meta` is carried for auditing; it is not sent upstream. Ordering carries no
information (aggregate counts drive every downstream decision), so specs are
fired in file order.

Every fired request carries `X-Run-Id`, so one run's traffic can be isolated in
the usage log without renaming the shared, server-owned file.

It carries no domain knowledge of its own. Correlated edge cases (schema mode)
come from `simulator.edge_cases`; the replay list (replay mode) comes from
whatever produced the file.

Usage:
    python scripts/simulate.py [BASE_URL] [N_REQUESTS] [--replay FILE] [--run-id ID]

Defaults come from flywheel.toml ([app].base_url, [simulator].default_requests,
[traffic].replay_file).
"""
import argparse
import json
import random
import re
import sys
from pathlib import Path
from urllib.parse import urljoin, urlsplit
from uuid import uuid4

import httpx
from flywheel_config import load_config, load_edge_cases

CONFIG = load_config()

# Endpoints that *describe* the API rather than being part of it — skip them.
SKIP_PATHS = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}

# Correlated edge cases, keyed by the value of an enum-driven param (e.g. `op`).
# Loaded from the file named by [simulator].edge_cases in flywheel.toml, so the
# simulator itself stays free of domain knowledge. Empty overlay is supported.
DOMAIN_EDGE_CASES: dict[str, list[dict]] = load_edge_cases(CONFIG)


def resolve_replay_path(cli_replay: str | None, config: dict) -> str | None:
    """Which replay file to use, or None for schema mode.

    Precedence: the --replay CLI flag wins; absent it, [traffic].replay_file from
    the active config applies; absent both, None (schema-random mode).
    """
    if cli_replay:
        return cli_replay
    configured = config.get("traffic", {}).get("replay_file")
    return configured or None


def load_replay_specs(path: str) -> list[dict]:
    """Parse a replay jsonl file into request specs, skipping blank lines."""
    lines = [ln for ln in Path(path).read_text().splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def safe_url(base_url: str, path: str) -> str:
    """Join `path` onto `base_url`, refusing anything that changes the origin.

    urljoin with a schema- or caller-controlled path can silently switch host
    (e.g. `//evil/collect` or an absolute URL), so verify the result stays on
    base_url's scheme+host before any request is sent.
    """
    joined = urljoin(base_url, path)
    b, j = urlsplit(base_url), urlsplit(joined)
    if (j.scheme, j.netloc) != (b.scheme, b.netloc):
        raise ValueError(f"refusing {path!r}: it leaves origin {b.scheme}://{b.netloc}")
    return joined


def fetch_schema(base_url: str) -> dict:
    """Fetch and parse /openapi.json, diagnosing a 200 that isn't really JSON.

    A proxy, captive portal, or auth wall can return HTTP 200 with an HTML error
    page instead of the schema — a real-world case, not an edge case (a status
    code alone does not prove the upstream is healthy). Raising a plain
    `JSONDecodeError` here would bury that behind a traceback pointing into
    httpx/json internals instead of naming the actual problem.
    """
    url = safe_url(base_url, "/openapi.json")
    r = httpx.get(url, timeout=10)
    r.raise_for_status()
    content_type = r.headers.get("content-type", "")
    if "json" not in content_type.lower():
        raise RuntimeError(
            f"{url} returned {r.status_code} with Content-Type {content_type!r}, not JSON — "
            f"looks like a proxy, captive portal, or auth wall serving an HTML page as a 200, "
            f"not the OpenAPI schema. Body starts: {r.text[:200]!r}"
        )
    try:
        return r.json()
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"{url} returned {r.status_code} with Content-Type {content_type!r} but the body is "
            f"not valid JSON ({e}). Body starts: {r.text[:200]!r}"
        ) from e


def resolve_ref(schema: dict, root: dict) -> dict:
    """Follow a $ref chain to the concrete schema object."""
    seen = 0
    while isinstance(schema, dict) and "$ref" in schema and seen < 10:
        name = schema["$ref"].split("/")[-1]
        schema = root.get("components", {}).get("schemas", {}).get(name, {})
        seen += 1
    return schema


def edgy_number(is_int: bool = False):
    """Random number, biased to include boundary values that produce signal."""
    if random.random() < 0.3:
        val = random.choice([0, -1, 1, 1e6, -1e6, 1e15, 0.001, -0.001])
    else:
        val = random.uniform(-100, 100)
    return int(val) if is_int else round(float(val), 3)


def gen_value(schema: dict, root: dict):
    """Synthesize a value from a JSON-schema fragment (handles $ref/enum/types)."""
    schema = resolve_ref(schema, root)
    if not isinstance(schema, dict):
        return None

    # Composition keywords. anyOf/oneOf: satisfy one branch. allOf: satisfy ALL
    # branches — merge their properties/required so no branch is dropped (a
    # first-branch-only shortcut omits required fields from the others).
    for key in ("anyOf", "oneOf"):
        if key in schema and schema[key]:
            return gen_value(random.choice(schema[key]), root)
    if "allOf" in schema and schema["allOf"]:
        merged: dict = {"type": "object", "properties": {}, "required": []}
        for sub in schema["allOf"]:
            sub = resolve_ref(sub, root)
            if isinstance(sub, dict):
                merged["properties"].update(sub.get("properties", {}))
                merged["required"] += sub.get("required", [])
        return gen_value(merged, root)

    if "enum" in schema:
        return random.choice(schema["enum"])

    t = schema.get("type")
    if t == "integer":
        return edgy_number(is_int=True)
    if t == "number":
        return edgy_number()
    if t == "boolean":
        return random.choice([True, False])
    if t == "array":
        return [gen_value(schema.get("items", {}), root) for _ in range(random.randint(1, 3))]
    if t == "object" or "properties" in schema:
        return {k: gen_value(v, root) for k, v in schema.get("properties", {}).items()}
    if t == "string":
        return random.choice(["test", "alpha", "sample"])
    return None


def _resolve_param(p: dict, root: dict) -> dict:
    """Resolve a parameter that is itself a $ref into components/parameters."""
    if isinstance(p, dict) and "$ref" in p:
        name = p["$ref"].split("/")[-1]
        return root.get("components", {}).get("parameters", {}).get(name, {})
    return p


def effective_parameters(op_spec: dict, path_item: dict, root: dict) -> list[dict]:
    """Parameters that actually apply to an operation.

    Per OpenAPI, parameters declared at the path-item level apply to every
    operation under that path; an operation's own parameters override them by
    (name, location). $ref parameters are resolved. Skipping path-level params
    is why templated paths like /items/{item_id} were left unsubstituted.
    """
    merged: dict[tuple, dict] = {}
    for p in list(path_item.get("parameters", [])) + list(op_spec.get("parameters", [])):
        p = _resolve_param(p, root)
        if isinstance(p, dict) and "name" in p and "in" in p:
            merged[(p["name"], p["in"])] = p
    return list(merged.values())


def has_inputs(op_spec: dict, params: list[dict]) -> bool:
    """True if the operation takes any params or a request body (worth firing repeatedly)."""
    return bool(params) or bool(op_spec.get("requestBody"))


def build_request(path: str, op_spec: dict, params: list[dict], root: dict):
    """Return (filled_path, query_params, json_body) synthesized from the schema.

    `params` is the already-merged effective parameter list (path-level +
    operation-level, $refs resolved). Only application/json request bodies are
    synthesized; other media types are not.
    """
    path_params, query_params = {}, {}
    for p in params:
        val = gen_value(p.get("schema", {}), root)
        if p.get("in") == "path":
            path_params[p["name"]] = val
        elif p.get("in") == "query":
            query_params[p["name"]] = val

    json_body = None
    content = op_spec.get("requestBody", {}).get("content", {}).get("application/json", {})
    if content:
        json_body = gen_value(content.get("schema", {}), root)

    # Optional domain overlay: if ANY generated param value matches a known
    # edge-case key, inject correlated values (40%). Not tied to a specific
    # param name — works for any enum-driven param the schema exposes.
    for pval in list(query_params.values()):
        if isinstance(pval, str) and pval in DOMAIN_EDGE_CASES and random.random() < 0.4:
            query_params.update(random.choice(DOMAIN_EDGE_CASES[pval]))
            break

    filled = path
    for name, val in path_params.items():
        filled = filled.replace("{" + name + "}", str(val) if val is not None else "1")
    # Fill any remaining template var (undeclared path param) so we never request
    # a literal "{id}", which would always 404 and pollute the demand signal.
    filled = re.sub(r"\{[^}]+\}", "1", filled)
    return filled, query_params, json_body


def discover(schema: dict):
    """Return (path, method, spec, params) for every real operation in the schema.

    `params` is the effective parameter list (path-level merged in, $refs
    resolved), computed once here so every consumer sees the same view.
    """
    operations = []
    for path, item in schema.get("paths", {}).items():
        if path in SKIP_PATHS:
            continue
        for method, spec in item.items():
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                params = effective_parameters(spec, item, schema)
                operations.append((path, method.lower(), spec, params))
    return operations


def print_enum_params(operations, root):
    """Surface enum-valued params (e.g. op) so loop-closure on new ops is visible."""
    for path, method, _spec, params in operations:
        for p in params:
            ps = resolve_ref(p.get("schema", {}), root)
            if isinstance(ps, dict) and "enum" in ps:
                print(f"    {method.upper()} {path}  {p['name']} ∈ {ps['enum']}")


def fire(base_url: str, method: str, path: str, params, body, label: str, idx: int, stats: dict, run_id: str):
    """Fire one request, record its outcome in stats, and log a line."""
    stats.setdefault(label, {"total": 0, "errors": 0})
    headers = {"X-Usage-Source": "simulator", "X-Run-Id": run_id}
    try:
        url = safe_url(base_url, path)
        r = httpx.request(method, url, params=params or None, json=body, headers=headers, timeout=5)
        status = r.status_code
        stats[label]["total"] += 1
        if status >= 400:
            stats[label]["errors"] += 1
        tag = "ERR" if status >= 400 else " OK"
        detail = f"q={params}" if params else (f"body={body}" if body else "")
        print(f"[{idx + 1:02d}] {tag} {label:22s} {detail} → {status}")
    except Exception as e:
        stats[label]["total"] += 1
        stats[label]["errors"] += 1
        print(f"[{idx + 1:02d}] EXC {label:22s} → {e}")


def print_summary(stats: dict):
    print("\n── Summary ──────────────────────────────────")
    for label, c in sorted(stats.items()):
        pct = c["errors"] / c["total"] * 100 if c["total"] else 0
        print(f"  {label:22s}: {c['total']:3d} calls, {c['errors']:3d} errors ({pct:.0f}%)")
    print("\nUsage data appended to the server's usage log.")
    print("Run /dev-loop in Claude Code to analyze and propose features.")


def run_replay(base_url: str, replay_path: str, run_id: str) -> dict:
    specs = load_replay_specs(replay_path)
    print(f"Replaying {len(specs)} recorded requests from {replay_path}  (run_id={run_id})\n")
    stats: dict[str, dict] = {}
    for i, spec in enumerate(specs):
        method = str(spec.get("method", "GET")).lower()
        path = spec["path"]
        label = f"{method.upper()} {path}"
        fire(base_url, method, path, spec.get("query"), spec.get("body"), label, i, stats, run_id)
    return stats


def run_schema(base_url: str, n_requests: int, run_id: str) -> dict:
    print(f"Fetching schema from {base_url}/openapi.json ...")
    schema = fetch_schema(base_url)

    operations = discover(schema)
    if not operations:
        raise RuntimeError("No operations found in /openapi.json — nothing to exercise.")

    labels = [f"{m.upper()} {p}" for p, m, _, _ in operations]
    print(f"Discovered {len(operations)} operations: {labels}")
    print_enum_params(operations, schema)

    # Coverage pass (hit each op once) + weighted remainder toward ops with inputs.
    pool = [o for o in operations if has_inputs(o[2], o[3])] or operations
    sequence = list(operations) + [random.choice(pool) for _ in range(max(0, n_requests - len(operations)))]
    sequence = sequence[:n_requests]
    random.shuffle(sequence)

    print(f"Firing {len(sequence)} requests  (run_id={run_id})\n")
    stats: dict[str, dict] = {}
    for i, (path, method, spec, params) in enumerate(sequence):
        label = f"{method.upper()} {path}"
        filled, qp, body = build_request(path, spec, params, schema)
        fire(base_url, method, filled, qp, body, label, i, stats, run_id)
    return stats


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Schema-driven / replay API simulator")
    ap.add_argument("base_url", nargs="?", default=CONFIG["app"]["base_url"])
    ap.add_argument("n_requests", nargs="?", type=int, default=CONFIG["simulator"]["default_requests"])
    ap.add_argument("--replay", default=None, help="replay jsonl path; overrides [traffic].replay_file")
    ap.add_argument("--run-id", default=None, help="tag this run's traffic (default: a random sim-* id)")
    return ap.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    run_id = args.run_id or f"sim-{uuid4().hex[:8]}"
    replay_path = resolve_replay_path(args.replay, CONFIG)

    print(f"Simulator → {args.base_url}")
    if replay_path:
        stats = run_replay(args.base_url, replay_path, run_id)
    else:
        stats = run_schema(args.base_url, args.n_requests, run_id)
    print_summary(stats)


if __name__ == "__main__":
    sys.exit(main())
