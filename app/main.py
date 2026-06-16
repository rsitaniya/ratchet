import json
import math
import time
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

from fastapi import FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

USAGE_LOG = Path("usage_log.jsonl")

app = FastAPI(
    title="Calculator API",
    description="""
A minimal arithmetic calculator exposing five operations over HTTP.

## Usage Signal

Every request to `/calculate` is appended to `usage_log.jsonl` with full context:
`timestamp`, `operation`, `inputs`, `status_code`, `latency_ms`, `error_type`.

This file is the **product signal** the feature-suggester agent reads to identify
gaps — e.g. "divide returned DivisionByZero in 27% of calls → add safe-divide or modulo."

## Operations

| `op`       | Formula | Edge case |
|------------|---------|-----------|
| `add`      | a + b   | —         |
| `subtract` | a − b   | —         |
| `multiply` | a × b   | —         |
| `divide`   | a ÷ b   | b=0 → HTTP 400 DivisionByZero |
| `mod`      | a % b   | b=0 → HTTP 400 DivisionByZero |

## Agentic Dev Loop

Invoke `/dev-loop` in Claude Code to run a full feature-shipping cycle:
simulate → suggest → human approves → implement → test → docs → repeat.
""",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


class Operation(str, Enum):
    add = "add"
    subtract = "subtract"
    multiply = "multiply"
    divide = "divide"
    mod = "mod"


class CalculateResponse(BaseModel):
    result: float = Field(..., description="Arithmetic result of op(a, b)")
    op: str = Field(..., description="Operation that was performed")
    a: float = Field(..., description="First operand")
    b: float = Field(..., description="Second operand")


class ErrorResponse(BaseModel):
    error: str = Field(..., description="Human-readable error message")
    error_type: str = Field(..., description="Machine-readable error classification")


@app.middleware("http")
async def usage_logger(request: Request, call_next):
    start_ns = time.perf_counter_ns()
    response = await call_next(request)
    latency_ms = round((time.perf_counter_ns() - start_ns) / 1_000_000, 2)

    if request.url.path == "/calculate":
        params = request.query_params
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "operation": params.get("op"),
            "inputs": {"a": params.get("a"), "b": params.get("b")},
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "error_type": getattr(request.state, "error_type", None),
            "source": request.headers.get("x-usage-source", "unknown"),
        }
        with USAGE_LOG.open("a") as f:
            f.write(json.dumps(record) + "\n")

    return response


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
- `mod` — modulo (remainder); returns **HTTP 400** with `error_type: DivisionByZero` when `b = 0`

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
    op: Operation = Query(..., description="Arithmetic operation: add | subtract | multiply | divide | mod"),
    a: float = Query(..., description="First operand — supports negatives, floats, large numbers"),
    b: float = Query(..., description="Second operand — b=0 triggers DivisionByZero error for divide and mod"),
) -> CalculateResponse:
    for name, value in (("a", a), ("b", b)):
        if not math.isfinite(value):
            request.state.error_type = "NonFiniteInput"
            return JSONResponse(
                status_code=422,
                content={"error": f"Operand {name} must be a finite number", "error_type": "NonFiniteInput"},
            )

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
        Operation.divide: lambda: a / b,
        Operation.mod: lambda: a % b,
    }
    result = ops[op]()
    if not math.isfinite(result):
        request.state.error_type = "Overflow"
        return JSONResponse(
            status_code=400,
            content={"error": "Result is not a finite number (overflow)", "error_type": "Overflow"},
        )
    return CalculateResponse(result=result, op=op.value, a=a, b=b)


@app.get("/health", summary="Health check", description="Returns `{status: ok}` if the service is running.")
async def health():
    return {"status": "ok"}
