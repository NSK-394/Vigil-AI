"""
api_server.py — FastAPI ingestion server for VigilAI.

Every incoming HTTP request is timed and logged into the shared SQLite queue
(live_queue.py). The Streamlit dashboard drains that queue each cycle via
MonitorAgent, so the two processes never share in-memory state.

Start with:
    python run_server.py
  or:
    cd src && uvicorn api_server:app --host 0.0.0.0 --port 8000 --reload

Test endpoints:
    GET/POST  /api/login
    GET       /api/products
    GET       /api/user
    GET       /api/search
    GET       /api/orders
    GET       /health          ← returns queue depth
"""

from __future__ import annotations

import sys
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Ensure src/ is on the path when uvicorn is launched from the project root
_src = os.path.dirname(os.path.abspath(__file__))
if _src not in sys.path:
    sys.path.insert(0, _src)

from live_queue import push, queue_size

app = FastAPI(title="VigilAI Ingestion Server", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Endpoints to skip logging (internal / health) ─────────────────────────────
_SKIP_PATHS = {"/docs", "/openapi.json", "/health", "/favicon.ico"}


# ── Middleware ────────────────────────────────────────────────────────────────

@app.middleware("http")
async def capture_request(request: Request, call_next):
    """
    Intercept every non-internal request, measure latency, and push a
    normalised log dict into the shared SQLite queue.
    """
    start    = time.perf_counter()
    response = await call_next(request)
    latency  = round(time.perf_counter() - start, 4)

    if request.url.path not in _SKIP_PATHS:
        api_key = (
            request.headers.get("x-api-key")
            or request.headers.get("authorization", "").replace("Bearer ", "").strip()
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
            # Fields expected by feature_extractor
            "request_count": 1,
            "attack_type":   "real",
        }
        push(log)

    return response


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "queue_depth": queue_size()}


# ── Test endpoints ────────────────────────────────────────────────────────────

@app.get("/api/login")
@app.post("/api/login")
async def login(request: Request):
    return JSONResponse({"message": "Login endpoint", "method": request.method})


@app.get("/api/products")
async def products():
    return JSONResponse({"products": ["item_001", "item_002", "item_003"]})


@app.get("/api/user")
async def user_profile(request: Request):
    return JSONResponse({"user": request.headers.get("x-api-key", "anonymous")})


@app.get("/api/search")
async def search(q: str = ""):
    return JSONResponse({"query": q, "results": []})


@app.get("/api/orders")
async def orders():
    return JSONResponse({"orders": []})
