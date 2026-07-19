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
and error codes plus a HASHED record id — never raw customer values.
"""
import hashlib
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from engagements.madi_onboarding import adapters as A

ENGAGEMENT_DIR = Path(__file__).resolve().parent.parent
TARGET_SCHEMA = json.loads((ENGAGEMENT_DIR / "fixtures" / "target_schema.json").read_text())
ADAPTERS_DIR = ENGAGEMENT_DIR / "adapters"

# Same seam as the calculator app (PR1): the launcher exports USAGE_LOG_PATH from
# [app].usage_log so server and analyzer agree on the file.
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


class IngestRequest(BaseModel):
    source_system: str = Field(..., description="Which partner system the record came from")
    schema_version: str = Field("v1", description="Partner schema version")
    record: dict = Field(..., description="One raw partner record (may include a 'record_id')")


def _hash_id(record_id) -> str:
    return hashlib.sha256(str(record_id).encode()).hexdigest()[:12]


def _emit(events: list[dict]) -> None:
    with USAGE_LOG.open("a") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")


@app.middleware("http")
async def usage_logger(request: Request, call_next):
    start = time.perf_counter_ns()
    response = await call_next(request)
    if request.url.path not in SKIP_USAGE_PATHS:
        _emit([{
            "timestamp": datetime.now(UTC).isoformat(),
            "event": "http",
            "path": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "latency_ms": round((time.perf_counter_ns() - start) / 1_000_000, 2),
            "source": request.headers.get("x-usage-source", "unknown"),
            "run_id": request.headers.get("x-run-id"),
        }])
    return response


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


@app.get("/health", summary="Health check")
async def health():
    return {"status": "ok"}
