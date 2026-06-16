#!/usr/bin/env python3
"""
Schema-driven API simulator.

Fetches /openapi.json from a running server, discovers available operations,
then fires N requests — mixing realistic inputs with targeted edge cases so
usage_log.jsonl accumulates meaningful product signal.

Usage:
    python scripts/simulate.py [BASE_URL] [N_REQUESTS]

Defaults: BASE_URL=http://localhost:8000, N_REQUESTS=30
"""
import json
import random
import sys
from urllib.parse import urljoin

import httpx

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
N_REQUESTS = int(sys.argv[2]) if len(sys.argv) > 2 else 30

# Domain edge cases keyed by operation name.
# The schema only tells us types; we inject domain knowledge for interesting signal.
DOMAIN_EDGE_CASES: dict[str, list[dict]] = {
    "divide": [
        {"a": 10, "b": 0},         # DivisionByZero — creates error signal
        {"a": -5, "b": 2},         # negative numerator
        {"a": 1, "b": 3},          # repeating decimal
        {"a": 1e9, "b": 3},        # large number
        {"a": 0.001, "b": 0.001},  # tiny floats
        {"a": 0, "b": 5},          # zero numerator
    ],
    "multiply": [
        {"a": 0, "b": 999},
        {"a": -3, "b": -4},        # negative × negative
        {"a": 1e6, "b": 1e6},      # large product
        {"a": 0.1, "b": 0.2},      # float precision
    ],
    "add": [
        {"a": 1e15, "b": 1e15},
        {"a": -1000, "b": 1000},   # cancellation
        {"a": 0, "b": 0},
    ],
    "subtract": [
        {"a": 0, "b": 1000},       # negative result
        {"a": -5, "b": -3},        # double negative
        {"a": 1.0, "b": 0.9},      # float subtraction
    ],
    "mod": [
        {"a": 10, "b": 0},         # DivisionByZero — creates error signal
        {"a": -7, "b": 3},         # negative dividend (Python: result is 2)
        {"a": 7, "b": -3},         # negative divisor (Python: result is -2)
        {"a": 10, "b": 10},        # result = 0 edge case
    ],
}


def fetch_schema(base_url: str) -> dict:
    r = httpx.get(urljoin(base_url, "/openapi.json"), timeout=10)
    r.raise_for_status()
    return r.json()


def _resolve_ref(ref: str, schema: dict) -> dict:
    """Resolve a JSON $ref string against the schema components."""
    name = ref.split("/")[-1]
    return schema.get("components", {}).get("schemas", {}).get(name, {})


def extract_operations(schema: dict) -> list[str]:
    """Parse enum values for 'op' param from the OpenAPI schema.

    Handles three encodings FastAPI may produce:
      - direct $ref: {"$ref": "#/components/schemas/Operation"}
      - allOf wrapping: {"allOf": [{"$ref": "..."}]}
      - inline enum: {"enum": [...]}
    """
    for path_data in schema.get("paths", {}).values():
        for method_data in path_data.values():
            for param in method_data.get("parameters", []):
                if param.get("name") != "op":
                    continue
                param_schema = param.get("schema", {})

                # Direct $ref (FastAPI >= 0.99 with Annotated Query params)
                if "$ref" in param_schema:
                    resolved = _resolve_ref(param_schema["$ref"], schema)
                    if resolved.get("enum"):
                        return resolved["enum"]

                # allOf wrapping a $ref
                if "allOf" in param_schema:
                    ref = param_schema["allOf"][0].get("$ref", "")
                    resolved = _resolve_ref(ref, schema)
                    if resolved.get("enum"):
                        return resolved["enum"]

                # Inline enum
                if "enum" in param_schema:
                    return param_schema["enum"]

    # Fallback: no schema introspection available
    return ["add", "subtract", "multiply", "divide"]


def gen_inputs(op: str) -> dict:
    """40% edge cases, 60% random realistic inputs."""
    edge_cases = DOMAIN_EDGE_CASES.get(op, [])
    if edge_cases and random.random() < 0.4:
        return random.choice(edge_cases)
    return {
        "a": round(random.uniform(-100, 100), 3),
        "b": round(random.uniform(-100, 100), 3),
    }


def main() -> None:
    print(f"Simulator → {BASE_URL}")
    print(f"Fetching schema from {BASE_URL}/openapi.json ...")

    schema = fetch_schema(BASE_URL)
    ops = extract_operations(schema)
    print(f"Discovered operations: {ops}")
    print(f"Firing {N_REQUESTS} requests (40% edge cases)\n")

    counts: dict[str, dict] = {op: {"total": 0, "errors": 0} for op in ops}

    for i in range(N_REQUESTS):
        op = random.choice(ops)
        inputs = gen_inputs(op)
        params = {"op": op, **inputs}
        try:
            r = httpx.get(urljoin(BASE_URL, "/calculate"), params=params, timeout=5)
            status = r.status_code
            counts[op]["total"] += 1
            if status >= 400:
                counts[op]["errors"] += 1
            tag = "ERR" if status >= 400 else " OK"
            print(f"[{i+1:02d}] {tag} {op:10s}  a={inputs['a']:>10}  b={inputs['b']:>10}  → {status}")
        except Exception as e:
            counts[op]["total"] += 1
            counts[op]["errors"] += 1
            print(f"[{i+1:02d}] EXC {op:10s} → {e}")

    print("\n── Summary ──────────────────────────────────")
    for op, c in counts.items():
        err_pct = (c["errors"] / c["total"] * 100) if c["total"] else 0
        print(f"  {op:10s}: {c['total']:3d} calls, {c['errors']:3d} errors ({err_pct:.0f}%)")
    print(f"\nUsage data appended to usage_log.jsonl on the server.")
    print("Run /dev-loop in Claude Code to analyze and propose features.")


if __name__ == "__main__":
    main()
