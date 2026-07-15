#!/usr/bin/env python3
"""
Schema-driven, multi-endpoint API simulator.

Fetches /openapi.json and exercises EVERY operation it finds — each path +
method — by synthesizing requests from the parameter and request-body schemas.
It is generic by construction: when the API gains a new endpoint (a new GET or
POST, with query params, path params, or a JSON body), the simulator exercises
it automatically with no hand-editing, as long as it is described in
/openapi.json.

It carries no domain knowledge of its own. Correlated edge cases (e.g. op=divide
with b=0) are loaded from the file named by `simulator.edge_cases` in
flywheel.toml; if that overlay is absent the simulator still exercises every
endpoint using values synthesized from the schema alone. All request *structure*
— which endpoints exist, their methods, params, and body shapes — is derived from
the schema at runtime.

Usage:
    python scripts/simulate.py [BASE_URL] [N_REQUESTS]

Defaults come from flywheel.toml ([app].base_url, [simulator].default_requests).
"""
import random
import sys
from urllib.parse import urljoin

import httpx
from flywheel_config import load_config, load_edge_cases

CONFIG = load_config()

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else CONFIG["app"]["base_url"]
N_REQUESTS = int(sys.argv[2]) if len(sys.argv) > 2 else CONFIG["simulator"]["default_requests"]

# Endpoints that *describe* the API rather than being part of it — skip them.
SKIP_PATHS = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect"}

# Correlated edge cases, keyed by the value of an enum-driven param (e.g. `op`).
# Loaded from the file named by [simulator].edge_cases in flywheel.toml, so the
# simulator itself stays free of domain knowledge. Empty overlay is supported.
DOMAIN_EDGE_CASES: dict[str, list[dict]] = load_edge_cases(CONFIG)


def fetch_schema(base_url: str) -> dict:
    r = httpx.get(urljoin(base_url, "/openapi.json"), timeout=10)
    r.raise_for_status()
    return r.json()


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

    # Composition keywords: pick a branch (allOf → merge-ish, take first)
    for key in ("anyOf", "oneOf"):
        if key in schema and schema[key]:
            return gen_value(random.choice(schema[key]), root)
    if "allOf" in schema and schema["allOf"]:
        return gen_value(schema["allOf"][0], root)

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


def has_inputs(op_spec: dict) -> bool:
    """True if the operation takes any params or a request body (worth firing repeatedly)."""
    return bool(op_spec.get("parameters")) or bool(op_spec.get("requestBody"))


def build_request(path: str, op_spec: dict, root: dict):
    """Return (filled_path, query_params, json_body) synthesized from the schema."""
    path_params, query_params = {}, {}
    for p in op_spec.get("parameters", []):
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
        filled = filled.replace("{" + name + "}", str(val))
    return filled, query_params, json_body


def discover(schema: dict):
    """Return list of (path, method, spec) for every real operation in the schema."""
    operations = []
    for path, item in schema.get("paths", {}).items():
        if path in SKIP_PATHS:
            continue
        for method, spec in item.items():
            if method.lower() in ("get", "post", "put", "patch", "delete"):
                operations.append((path, method.lower(), spec))
    return operations


def print_enum_params(operations, root):
    """Surface enum-valued params (e.g. op) so loop-closure on new ops is visible."""
    for path, method, spec in operations:
        for p in spec.get("parameters", []):
            ps = resolve_ref(p.get("schema", {}), root)
            if isinstance(ps, dict) and "enum" in ps:
                print(f"    {method.upper()} {path}  {p['name']} ∈ {ps['enum']}")


def main() -> None:
    print(f"Simulator → {BASE_URL}")
    print(f"Fetching schema from {BASE_URL}/openapi.json ...")
    schema = fetch_schema(BASE_URL)

    operations = discover(schema)
    if not operations:
        raise RuntimeError("No operations found in /openapi.json — nothing to exercise.")

    labels = [f"{m.upper()} {p}" for p, m, _ in operations]
    print(f"Discovered {len(operations)} operations: {labels}")
    print_enum_params(operations, schema)

    # Coverage pass (hit each op once) + weighted remainder toward ops with inputs.
    pool = [o for o in operations if has_inputs(o[2])] or operations
    sequence = list(operations) + [random.choice(pool) for _ in range(max(0, N_REQUESTS - len(operations)))]
    sequence = sequence[:N_REQUESTS]
    random.shuffle(sequence)

    print(f"Firing {len(sequence)} requests\n")
    stats: dict[str, dict] = {}
    for i, (path, method, spec) in enumerate(sequence):
        label = f"{method.upper()} {path}"
        stats.setdefault(label, {"total": 0, "errors": 0})
        filled, qp, body = build_request(path, spec, schema)
        try:
            r = httpx.request(
                method, urljoin(BASE_URL, filled),
                params=qp or None, json=body,
                headers={"X-Usage-Source": "simulator"}, timeout=5,
            )
            status = r.status_code
            stats[label]["total"] += 1
            if status >= 400:
                stats[label]["errors"] += 1
            tag = "ERR" if status >= 400 else " OK"
            detail = f"q={qp}" if qp else (f"body={body}" if body else "")
            print(f"[{i + 1:02d}] {tag} {label:22s} {detail} → {status}")
        except Exception as e:
            stats[label]["total"] += 1
            stats[label]["errors"] += 1
            print(f"[{i + 1:02d}] EXC {label:22s} → {e}")

    print("\n── Summary ──────────────────────────────────")
    for label, c in sorted(stats.items()):
        pct = c["errors"] / c["total"] * 100 if c["total"] else 0
        print(f"  {label:22s}: {c['total']:3d} calls, {c['errors']:3d} errors ({pct:.0f}%)")
    print("\nUsage data appended to usage_log.jsonl on the server.")
    print("Run /dev-loop in Claude Code to analyze and propose features.")


if __name__ == "__main__":
    main()
