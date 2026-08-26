"""Partner-data onboarding API — the "customer" service the flywheel improves.

A partner sends records from its own system to a single stable endpoint:

    POST /ingest   {source_system, schema_version, record}

The service maps and normalizes the record to a canonical target schema using a
per-source *adapter* (declarative data under adapters/). A not-yet-onboarded
source has an empty adapter, so its records fail with structured errors. Those
errors are the product signal: the flywheel reads them, proposes the smallest
adapter change, and (after human approval + a held-out evaluation) grows the
adapter until the source integrates — without regressing already-onboarded ones.

Telemetry is structured and privacy-preserving: it records field NAMES, stages,
and error codes plus a KEYED-HMAC record id — never raw customer values, and
never a value an attacker who knows (or guesses) the id space can recompute
without the deployment's own key.
"""
import hashlib
import hmac
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engagements.madi_onboarding import adapters as A
from engagements.madi_onboarding import fusion, matching, similarity

ENGAGEMENT_DIR = Path(__file__).resolve().parent.parent
TARGET_SCHEMA = json.loads((ENGAGEMENT_DIR / "fixtures" / "target_schema.json").read_text())
ADAPTERS_DIR = ENGAGEMENT_DIR / "adapters"

# The launcher exports USAGE_LOG_PATH from [app].usage_log so server and
# analyzer agree on the file.
USAGE_LOG = Path(os.environ.get("USAGE_LOG_PATH", "usage_log.jsonl"))

SKIP_USAGE_PATHS = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect", "/health", "/favicon.ico"}

app = FastAPI(
    title="Partner Data Onboarding API",
    description=(
        "Ingests partner records into a canonical company schema via per-source "
        "adapters. Unmapped fields, bad values, and missing required attributes are "
        "recorded as structured integration signal for the dev-flywheel loop."
    ),
    version="0.1.0",
)


# A source system names an adapter file; constrain it at the API boundary so an
# unsafe value is a 422, never a path-traversal attempt. Reconcile inputs are
# bounded because matching is O(len(left) * len(right)).
SOURCE_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
MAX_RECORDS = 5000


class IngestRequest(BaseModel):
    source_system: str = Field(..., pattern=SOURCE_PATTERN, description="Which partner system the record came from")
    schema_version: str = Field("v1", max_length=32, description="Partner schema version")
    record: dict = Field(..., description="One raw partner record (may include a 'record_id')")


_DEV_HASH_KEY = b"dev-only-key-not-a-secret-set-RECORD_ID_HASH_KEY-in-any-real-deployment"


def _hash_id(record_id) -> str:
    """Keyed HMAC, not a bare hash: an unkeyed SHA-256 of a small, guessable id
    space (order numbers, SKUs, short customer ids) is a dictionary attack away
    from recovering exactly which telemetry row is which real record — keying
    it means recovery also requires the deployment's own secret."""
    key = os.environ.get("RECORD_ID_HASH_KEY", "").encode() or _DEV_HASH_KEY
    return hmac.new(key, str(record_id).encode(), hashlib.sha256).hexdigest()[:12]


def _emit(events: list[dict]) -> None:
    """Append telemetry events. Fail-open: a logging failure must never break a
    served request, so any write error is swallowed to stderr."""
    try:
        with USAGE_LOG.open("a") as f:
            for e in events:
                f.write(json.dumps(e) + "\n")
    except Exception as e:  # noqa: BLE001 — telemetry is best-effort, never fatal
        print(f"[usage-log] failed to record {len(events)} event(s): {e}", file=sys.stderr)


@app.middleware("http")
async def usage_logger(request: Request, call_next):
    start = time.perf_counter_ns()
    status_code = 500
    error_type = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        error_type = type(exc).__name__  # an unhandled crash still becomes signal
        raise
    finally:
        if request.url.path not in SKIP_USAGE_PATHS:
            _emit([{
                "timestamp": datetime.now(UTC).isoformat(),
                "event": "http",
                "path": request.url.path,
                "method": request.method,
                "status_code": status_code,
                "error_type": error_type,
                "latency_ms": round((time.perf_counter_ns() - start) / 1_000_000, 2),
                "source": request.headers.get("x-usage-source", "unknown"),
                "run_id": request.headers.get("x-run-id"),
            }])


@app.post("/ingest", summary="Ingest one partner record")
async def ingest(req: IngestRequest, request: Request):
    """Map + normalize one record to the target schema; record structured signal.

    Returns 200 with the integrated target record, or 422 with the structured
    failures (unmapped fields, invalid values, missing required attributes).
    """
    adapter = A.load_adapter(req.source_system, ADAPTERS_DIR)
    result = A.apply_adapter(req.record, adapter, TARGET_SCHEMA)

    rid_hash = _hash_id(req.record.get("record_id"))
    run_id = request.headers.get("x-run-id")
    now = datetime.now(UTC).isoformat()
    events: list[dict] = []
    for failure in result["failures"]:
        events.append({
            "timestamp": now, "event": "integration", "run_id": run_id,
            "source_system": req.source_system, "schema_version": req.schema_version,
            "record_id_hash": rid_hash, **failure,
        })
    events.append({
        "timestamp": now, "event": "record", "run_id": run_id,
        "source_system": req.source_system, "schema_version": req.schema_version,
        "record_id_hash": rid_hash, "integrated": result["integrated"],
        "n_failures": len(result["failures"]),
    })
    _emit(events)

    if result["integrated"]:
        return {"integrated": True, "target": result["target"]}
    return JSONResponse(status_code=422, content={"integrated": False, "failures": result["failures"]})


class ReconcileRequest(BaseModel):
    left_source: str = Field(..., pattern=SOURCE_PATTERN, description="Source system name for the left record set")
    right_source: str = Field(..., pattern=SOURCE_PATTERN, description="Source system name for the right record set")
    left: list[dict] = Field(..., max_length=MAX_RECORDS, description="Schema-mapped records from the left source")
    right: list[dict] = Field(..., max_length=MAX_RECORDS, description="Schema-mapped records from the right source")


@app.post("/reconcile", summary="Match + fuse records across two sources")
async def reconcile(req: ReconcileRequest, request: Request):
    """Entity-match the two record sets with the current matching rules, fuse each
    matched pair with the current fusion rules, and emit reconciliation signal:
    which records stayed unmatched, and which attributes conflict across matches.
    """
    # matching.match() raises on a missing record_id (an engine invariant, not an
    # HTTP concern) — check it here so a malformed record is a structured 422,
    # the same shape /ingest already returns, not an unhandled 500.
    missing_ids = [
        {"source": src, "index": i}
        for src, recs in (("left", req.left), ("right", req.right))
        for i, rec in enumerate(recs)
        if similarity.is_absent(rec.get("record_id"))
    ]
    if missing_ids:
        return JSONResponse(status_code=422, content={"error": "MISSING_RECORD_ID", "records": missing_ids})

    attrs = list(TARGET_SCHEMA["attributes"])
    predicted = matching.match(req.left, req.right, matching.load_rules())
    frules = fusion.load_rules()
    left_by = {r.get("record_id"): r for r in req.left}
    right_by = {r.get("record_id"): r for r in req.right}
    matched_left = {lid for lid, _ in predicted}
    matched_right = {rid for _, rid in predicted}

    run_id = request.headers.get("x-run-id")
    now = datetime.now(UTC).isoformat()
    events: list[dict] = []
    fused_out = []
    for lid, rid in predicted:
        cluster = [
            {"source": req.left_source, "record": left_by[lid]},
            {"source": req.right_source, "record": right_by[rid]},
        ]
        fused_out.append({"left_id": lid, "right_id": rid, "fused": fusion.fuse(cluster, frules, attrs)})
        for attr in attrs:
            lv, rv = left_by[lid].get(attr), right_by[rid].get(attr)
            if lv is not None and rv is not None and lv != rv:
                events.append({
                    "timestamp": now, "event": "reconcile", "run_id": run_id, "stage": "fusion",
                    "error_code": "ATTR_CONFLICT", "field": attr,
                    "record_id_hash": _hash_id(f"{lid}|{rid}"),
                })
    for rec in req.left:
        if rec.get("record_id") not in matched_left:
            events.append({
                "timestamp": now, "event": "reconcile", "run_id": run_id, "stage": "matching",
                "error_code": "UNMATCHED", "field": req.left_source,
                "record_id_hash": _hash_id(rec.get("record_id")),
            })
    for rec in req.right:
        if rec.get("record_id") not in matched_right:
            events.append({
                "timestamp": now, "event": "reconcile", "run_id": run_id, "stage": "matching",
                "error_code": "UNMATCHED", "field": req.right_source,
                "record_id_hash": _hash_id(rec.get("record_id")),
            })
    events.append({
        "timestamp": now, "event": "reconcile_summary", "run_id": run_id,
        "matched": len(predicted),
        "unmatched_left": len(req.left) - len(matched_left),
        "unmatched_right": len(req.right) - len(matched_right),
    })
    _emit(events)

    return {
        "matched": fused_out,
        "unmatched_left": [lid for lid in left_by if lid not in matched_left],
        "unmatched_right": [rid for rid in right_by if rid not in matched_right],
    }


@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok"}
