"""
middleware/ingest_server.py — VigilAI HTTP ingest server.

Receives log dicts from language-agnostic middleware (e.g. express_middleware.js)
and writes them to the shared SQLite queue for MonitorAgent to drain.

Start with:
    uvicorn src.middleware.ingest_server:app --host 0.0.0.0 --port 9000

Or set VIGIL_INGEST_PORT to override the default port (9000).

POST /ingest  — accepts any log dict; normalises field names from Express/external
GET  /health  — returns queue depth
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

# Resolve src/ so live_queue and other modules import correctly
# regardless of how uvicorn is launched (from project root or elsewhere).
_this_dir   = os.path.dirname(os.path.abspath(__file__))   # .../src/middleware
_src_dir    = os.path.dirname(_this_dir)                    # .../src
_root_dir   = os.path.dirname(_src_dir)                     # project root
for _p in (_src_dir, _root_dir):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from live_queue import push, queue_size

app = FastAPI(title="VigilAI Ingest Server", docs_url="/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


@app.post("/ingest")
async def ingest(request: Request) -> JSONResponse:
    """
    Accept a log dict from any middleware and push it to the VigilAI queue.

    Normalises Express field names (status_code, response_time) to the
    canonical names used throughout the pipeline (status, latency).
    Only api_key, endpoint, and request_count are strictly required by
    feature_extractor; all other fields default gracefully.
    """
    data = await request.json()

    log = {
        "api_key":       data.get("api_key", "anonymous"),
        "endpoint":      data.get("endpoint", "/"),
        "method":        data.get("method", "GET"),
        "status":        data.get("status") or data.get("status_code", 200),
        "latency":       data.get("latency") or data.get("response_time", 0.0),
        "ip_address":    data.get("ip_address", "unknown"),
        "timestamp":     data.get(
            "timestamp",
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        ),
        "request_count": min(int(data.get("request_count", 1)), 100_000),
        "attack_type":   data.get("attack_type", "real"),
    }

    push(log)
    return JSONResponse({"status": "ok"})


@app.get("/health")
async def health() -> JSONResponse:
    return JSONResponse({"status": "ok", "queue_depth": queue_size()})
