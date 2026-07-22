import json
import math
import os
import sys
import time
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Where the usage middleware appends records. The launcher (the loop's skills)
# exports USAGE_LOG_PATH from the active flywheel.toml's [app].usage_log so the
# server, analyzer, and any second app all agree on the file; absent that env
# var it falls back to the repo-root default, which is what the calculator uses.
USAGE_LOG = Path(os.environ.get("USAGE_LOG_PATH", "usage_log.jsonl"))

# Paths that describe or operate the service rather than being product surface.
# Traffic to these is infra noise, not usage signal — so it is NOT recorded.
# Everything else (including not-yet-implemented paths that 404) IS recorded,
# which is what lets the loop self-feed for any feature shape, not just new ops.
SKIP_USAGE_PATHS = {"/openapi.json", "/docs", "/redoc", "/docs/oauth2-redirect", "/health", "/favicon.ico"}

app = FastAPI(
    title="Calculator API",
    description=r"""
A minimal arithmetic calculator exposing seven operations over HTTP.

## Usage Signal

Every request to a product endpoint is appended to `usage_log.jsonl` with full
context: `timestamp`, `path`, `method`, `operation`, `inputs`, `status_code`,
`latency_ms`, `error_type`. Infra endpoints (`/health`, `/docs`, `/openapi.json`)
are skipped. Requests to paths that don't exist yet are still recorded (as 404s),
so "someone wanted this" becomes signal too.

This file is the **product signal** the feature-suggester agent reads to identify
gaps — e.g. "divide returned DivisionByZero in 27% of calls → add safe-divide or
modulo", or "GET /sqrt got 404 nine times → build that endpoint."

## Operations

| `op`       | Formula | Edge case |
|------------|---------|-----------|
| `add`      | a + b   | —         |
| `subtract` | a − b   | —         |
| `multiply` | a × b   | —         |
| `divide`   | a ÷ b   | b=0 → HTTP 400 DivisionByZero |
| `safe_divide` | a ÷ b   | b=0 → result=null |
| `mod`      | a % b   | b=0 → HTTP 400 DivisionByZero |
| `abs`      | \|a − b\| | —         |

## Agentic Dev Loop

Invoke `/dev-loop` in Claude Code to run a full feature-shipping cycle:
simulate → suggest → human approves → implement → test → docs → repeat.
""",
    version="0.5.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


class Operation(str, Enum):
    add = "add"
    subtract = "subtract"
    multiply = "multiply"
    divide = "divide"
    safe_divide = "safe_divide"
    mod = "mod"
    abs = "abs"


class CalculateResponse(BaseModel):
    result: float | None = Field(..., description="Arithmetic result of op(a, b); null for safe_divide when b=0")
    op: str = Field(..., description="Operation that was performed")
    a: float = Field(..., description="First operand")
    b: float = Field(..., description="Second operand")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Human-readable error message")
    error_type: str = Field(..., description="Machine-readable error classification")


class BatchItem(BaseModel):
    op: Operation = Field(
        ..., description="Arithmetic operation: add | subtract | multiply | divide | safe_divide | mod | abs"
    )
    a: float = Field(..., description="First operand")
    b: float = Field(..., description="Second operand")


class BatchResultItem(BaseModel):
    op: str = Field(..., description="Operation that was performed")
    a: float = Field(..., description="First operand")
    b: float = Field(..., description="Second operand")
    result: float | None = Field(None, description="Arithmetic result; null when an error occurred")
    error: str | None = Field(None, description="Human-readable error message; null on success")
    error_type: str | None = Field(None, description="Machine-readable error classification; null on success")


def _record_usage(request: Request, status_code: int, latency_ms: float, error_type: str | None) -> None:
    """Append one usage record. Fail-open: a logging failure must never turn a
    served request into an error, so any exception here is swallowed to stderr."""
    try:
        params = request.query_params
        record = {
            "timestamp": datetime.now(UTC).isoformat(),
            "path": request.url.path,
            "method": request.method,
            "operation": params.get("op"),
            "inputs": dict(params),
            "status_code": status_code,
            "latency_ms": latency_ms,
            "error_type": error_type,
            "source": request.headers.get("x-usage-source", "unknown"),
            "run_id": request.headers.get("x-run-id"),
        }
        with USAGE_LOG.open("a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:  # noqa: BLE001 — telemetry is best-effort, never fatal
        print(f"[usage-log] failed to record {request.url.path}: {e}", file=sys.stderr)


@app.middleware("http")
async def usage_logger(request: Request, call_next):
    start_ns = time.perf_counter_ns()
    status_code = 500
    error_type = None
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    except Exception as exc:
        # An unhandled handler exception still becomes signal (a 500 with the
        # exception name), instead of vanishing from the log entirely.
        error_type = type(exc).__name__
        raise
    finally:
        if request.url.path not in SKIP_USAGE_PATHS:
            latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)
            resolved_error = getattr(request.state, "error_type", None) or error_type
            _record_usage(request, status_code, latency_ms, resolved_error)


@app.get(
    "/calculate",
    response_model=CalculateResponse,
    responses={
        400: {"model": ErrorResponse, "description": "DivisionByZero (b=0) or numeric Overflow (result not finite)"},
        422: {"model": ErrorResponse, "description": "NonFiniteInput — operand is nan, inf, or -inf"},
    },
    summary="Perform arithmetic",
    description="""
Compute `op(a, b)` and return the result.

### Supported operations
- `add` — addition
- `subtract` — subtraction
- `multiply` — multiplication
- `divide` — division; returns **HTTP 400** with `error_type: DivisionByZero` when `b = 0`
- `safe_divide` — safe division; returns result=`null` when `b = 0`, no HTTP error
- `mod` — modulo (remainder); returns **HTTP 400** with `error_type: DivisionByZero` when `b = 0`
- `abs` — absolute difference; returns `|a - b|`

### Inputs
Operands support negative numbers, floats, and very large values.
Non-finite operands (`nan`, `inf`, `-inf`) are rejected with **HTTP 422**
(`error_type: NonFiniteInput`). Computations that overflow to a non-finite
result return **HTTP 400** (`error_type: Overflow`).

### Usage logging
Every call is recorded to `usage_log.jsonl`. The agentic feature-suggester reads
this file to find patterns (error rates, input distributions) and propose new features.
""",
)
async def calculate(
    request: Request,
    op: Operation = Query(
        ..., description="Arithmetic operation: add | subtract | multiply | divide | safe_divide | mod | abs"
    ),
    a: float = Query(..., description="First operand — supports negatives, floats, large numbers"),
    b: float = Query(
        ...,
        description="Second operand — b=0 triggers DivisionByZero error for divide and mod; safe_divide returns null",
    ),
) -> CalculateResponse:
    for name, value in (("a", a), ("b", b)):
        if not math.isfinite(value):
            request.state.error_type = "NonFiniteInput"
            return JSONResponse(
                status_code=422,
                content={"error": f"Operand {name} must be a finite number", "error_type": "NonFiniteInput"},
            )

    if op == Operation.safe_divide and b == 0:
        return CalculateResponse(result=None, op=op.value, a=a, b=b)

    if op in (Operation.divide, Operation.mod) and b == 0:
        request.state.error_type = "DivisionByZero"
        return JSONResponse(
            status_code=400,
            content={"error": "Division by zero is undefined", "error_type": "DivisionByZero"},
        )

    ops = {
        Operation.add: lambda: a + b,
        Operation.subtract: lambda: a - b,
        Operation.multiply: lambda: a * b,
        Operation.safe_divide: lambda: a / b,
        Operation.divide: lambda: a / b,
        Operation.mod: lambda: a % b,
        Operation.abs: lambda: abs(a - b),
    }
    result = ops[op]()
    if not math.isfinite(result):
        request.state.error_type = "Overflow"
        return JSONResponse(
            status_code=400,
            content={"error": "Result is not a finite number (overflow)", "error_type": "Overflow"},
        )
    return CalculateResponse(result=result, op=op.value, a=a, b=b)


@app.post(
    "/calculate/batch",
    response_model=list[BatchResultItem],
    responses={
        200: {
            "description": (
                "Array of results in request order; same length as input. Each item contains "
                "either `result` (float) on success or `error`/`error_type` on per-item failure."
            )
        },
        422: {"model": ErrorResponse, "description": "Malformed request body (invalid op, non-numeric operand, etc.)"},
    },
    summary="Run a batch of arithmetic operations",
    description="""
Compute multiple `op(a, b)` operations in a single round-trip.

Send a JSON array of `{op, a, b}` objects; receive an array of results in the
same order. Each item in the response carries the original `op`, `a`, `b` and
either a `result` (on success) or `error` / `error_type` (on failure).

Per-item errors (`DivisionByZero`, `Overflow`, `NonFiniteInput`) do **not** abort
the whole batch — every item is evaluated independently and the response always
has the same length as the request.

### Supported operations
- `add` — addition
- `subtract` — subtraction
- `multiply` — multiplication
- `divide` — division; `error_type: DivisionByZero` when `b = 0`
- `safe_divide` — safe division; result=`null` when `b = 0`, no error
- `mod` — modulo (remainder); `error_type: DivisionByZero` when `b = 0`
- `abs` — absolute difference; returns `|a - b|`
""",
)
async def calculate_batch(
    body: Annotated[list[BatchItem], Field(max_length=1000)],
) -> list[BatchResultItem]:
    results: list[BatchResultItem] = []
    for item in body:
        op, a, b = item.op, item.a, item.b

        for name, value in (("a", a), ("b", b)):
            if not math.isfinite(value):
                results.append(BatchResultItem(
                    op=op.value, a=a, b=b,
                    error=f"Operand {name} must be a finite number",
                    error_type="NonFiniteInput",
                ))
                break
        else:
            if op == Operation.safe_divide and b == 0:
                results.append(BatchResultItem(op=op.value, a=a, b=b, result=None))
            elif op in (Operation.divide, Operation.mod) and b == 0:
                results.append(BatchResultItem(
                    op=op.value, a=a, b=b,
                    error="Division by zero is undefined",
                    error_type="DivisionByZero",
                ))
            else:
                # Operands are bound as defaults so each lambda captures this
                # iteration's values rather than the loop variable.
                ops = {
                    Operation.add: lambda a=a, b=b: a + b,
                    Operation.subtract: lambda a=a, b=b: a - b,
                    Operation.multiply: lambda a=a, b=b: a * b,
                    Operation.safe_divide: lambda a=a, b=b: a / b,
                    Operation.divide: lambda a=a, b=b: a / b,
                    Operation.mod: lambda a=a, b=b: a % b,
                    Operation.abs: lambda a=a, b=b: abs(a - b),
                }
                result = ops[op]()
                if not math.isfinite(result):
                    results.append(BatchResultItem(
                        op=op.value, a=a, b=b,
                        error="Result is not a finite number (overflow)",
                        error_type="Overflow",
                    ))
                else:
                    results.append(BatchResultItem(op=op.value, a=a, b=b, result=result))
    return results


@app.get("/health", summary="Health check", description="Returns `{status: ok}` if the service is running.")
async def health():
    return {"status": "ok"}
