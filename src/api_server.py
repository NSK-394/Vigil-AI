"""
api_server.py — FastAPI ingestion server for VigilAI.

Captures real API traffic via middleware and feeds it into the shared
log buffer. MonitorAgent drains this buffer on each observe() cycle
when source="real".

Run alongside the dashboard:
    uvicorn src.api_server:app --host 0.0.0.0 --port 8000 --reload

Test endpoints are live at:
    GET  /api/login
    POST /api/login
    GET  /api/products
    GET  /api/user
    GET  /health
"""

from __future__ import annotations

import time
from collections import deque
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="VigilAI Ingestion Server", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Shared log buffer ─────────────────────────────────────────────────────────
# Thread-safe for single-writer (middleware) + single-reader (MonitorAgent).
# deque.append / deque.popleft are atomic under CPython's GIL.
_LOG_BUFFER: deque[dict] = deque(maxlen=50_000)


def get_buffer() -> deque[dict]:
    """Return the module-level log buffer (used by MonitorAgent)."""
    return _LOG_BUFFER


def ingest_log(log: dict) -> None:
    """
    Push a pre-built log dict directly into the buffer.
    Use this for programmatic injection (tests, external integrations).
    The dict must contain at minimum: api_key, endpoint, request_count.
    """
    _LOG_BUFFER.append(_normalize_external(log))


def drain_logs(max_items: int = 5000) -> list[dict]:
    """
    Pop up to max_items logs from the buffer and return them.
    Called by MonitorAgent._generate_real() on each observe cycle.
    """
    batch = []
    for _ in range(min(max_items, len(_LOG_BUFFER))):
        try:
            batch.append(_LOG_BUFFER.popleft())
        except IndexError:
            break
    return batch


# ── Middleware ────────────────────────────────────────────────────────────────

@app.middleware("http")
async def capture_request(request: Request, call_next):
    """
    Intercept every request, time it, and push a normalized log entry
    into the shared buffer after the response is generated.
    """
    start = time.perf_counter()
    response = await call_next(request)
    latency  = round(time.perf_counter() - start, 4)

    api_key = (
        request.headers.get("x-api-key")
        or request.headers.get("authorization", "").replace("Bearer ", "")
        or request.query_params.get("api_key")
        or "anonymous"
    )

    log = {
        "api_key":       api_key,
        "endpoint":      request.url.path,
        "method":        request.method,
        "status":        response.status_code,
        "latency":       latency,
        "ip_address":    request.client.host if request.client else "unknown",
        "timestamp":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        # Normalized fields expected by feature_extractor
        "request_count": 1,
        "attack_type":   "real",
    }

    # Skip internal FastAPI routes to avoid noise
    if not request.url.path.startswith(("/docs", "/openapi", "/health")):
        _LOG_BUFFER.append(log)

    return response


# ── Test endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "buffer_size": len(_LOG_BUFFER)}


@app.get("/api/login")
@app.post("/api/login")
async def login(request: Request):
    return JSONResponse({"message": "Login endpoint", "method": request.method})


@app.get("/api/products")
async def products():
    return JSONResponse({"products": ["item_001", "item_002", "item_003"]})


@app.get("/api/user")
async def user_profile(request: Request):
    api_key = request.headers.get("x-api-key", "anonymous")
    return JSONResponse({"user": api_key, "role": "standard"})


@app.get("/api/search")
async def search(q: str = ""):
    return JSONResponse({"query": q, "results": []})


@app.get("/api/orders")
async def orders():
    return JSONResponse({"orders": []})


# ── Internal helpers ──────────────────────────────────────────────────────────

def _normalize_external(log: dict) -> dict:
    """Ensure manually-ingested dicts have all required fields."""
    return {
        "api_key":       log.get("api_key", "unknown"),
        "endpoint":      log.get("endpoint", "/unknown"),
        "request_count": int(log.get("request_count", log.get("count", 1))),
        "timestamp":     log.get("timestamp", datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")),
        "ip_address":    log.get("ip_address", "0.0.0.0"),
        "method":        log.get("method", "GET"),
        "status":        int(log.get("status", 200)),
        "latency":       float(log.get("latency", 0.0)),
        "attack_type":   log.get("attack_type", "real"),
    }
