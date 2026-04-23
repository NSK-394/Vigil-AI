"""
middleware/fastapi_middleware.py — VigilAI drop-in middleware for FastAPI apps.

Captures every HTTP request and feeds it into the VigilAI detection pipeline
via a sliding-window request counter. Non-blocking by design.

Usage (3 lines):
    from src.middleware.fastapi_middleware import VigilMiddleware
    app = FastAPI()
    app.add_middleware(VigilMiddleware, vigil_url="http://localhost:9000/ingest")

Parameters:
    vigil_url       HTTP endpoint of the VigilAI ingest server (default: localhost:9000/ingest)
    window_seconds  Sliding window length for per-key request counting (default: 60)
    direct          True → push directly to live_queue (same-process / test use only)
                    False → POST to vigil_url asynchronously (default, production use)

The `request_count` field in each pushed log is the cumulative count of requests
for that api_key within the current window. This is what makes volume-based attack
detection work: an api_key firing 20 rapid requests will have a running series
[1, 2, ..., 20], giving the feature extractor a measurable request_variance and
a meaningful average_requests — unlike naive request_count=1 per log.

Thread safety: _counters is safe under uvicorn's default single-worker async mode
(single-threaded event loop). In multi-worker deployments each worker has its own
counter dict — counts are per-worker, not global.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timezone

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_SKIP_PATHS = {"/docs", "/openapi.json", "/health", "/favicon.ico"}


class VigilMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        vigil_url:      str   = "http://localhost:9000/ingest",
        window_seconds: int   = 60,
        direct:         bool  = False,
    ):
        super().__init__(app)
        self._vigil_url      = vigil_url
        self._window_seconds = window_seconds
        self._direct         = direct
        # {api_key: {"count": int, "window_start": float}}
        self._counters: dict[str, dict] = {}

    async def dispatch(self, request: Request, call_next):
        start    = time.monotonic()
        response = await call_next(request)
        latency  = round(time.monotonic() - start, 4)

        if request.url.path in _SKIP_PATHS:
            return response

        api_key       = self._get_api_key(request)
        request_count = self._increment(api_key)

        log = {
            "api_key":       api_key,
            "endpoint":      request.url.path,
            "method":        request.method,
            "status_code":   response.status_code,
            "response_time": latency,
            "ip_address":    request.client.host if request.client else "unknown",
            "timestamp":     datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            "request_count": request_count,
            "attack_type":   "real",
        }

        if self._direct:
            _src = os.path.join(os.path.dirname(__file__), "..")
            if _src not in sys.path:
                sys.path.insert(0, os.path.abspath(_src))
            from live_queue import push
            push(log)
        else:
            asyncio.create_task(self._send_async(log))

        return response

    def _get_api_key(self, request: Request) -> str:
        key = request.headers.get("x-api-key", "")
        if key:
            return key

        auth = request.headers.get("authorization", "")
        if auth.startswith("Bearer "):
            bearer = auth[len("Bearer "):].strip()
            if bearer:
                return bearer

        key = request.query_params.get("api_key", "")
        if key:
            return key

        return "anonymous"

    def _increment(self, api_key: str) -> int:
        now = time.monotonic()
        if api_key not in self._counters:
            self._counters[api_key] = {"count": 0, "window_start": now}
        entry = self._counters[api_key]
        if now - entry["window_start"] >= self._window_seconds:
            entry["count"]        = 0
            entry["window_start"] = now
        entry["count"] += 1
        return entry["count"]

    async def _send_async(self, log: dict) -> None:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                await client.post(self._vigil_url, json=log)
        except Exception:
            pass
