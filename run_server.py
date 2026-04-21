"""
run_server.py — FastAPI ingestion server launcher.

Sets up sys.path correctly so api_server.py and all src/ modules
(including live_queue.py) resolve regardless of CWD.

Usage:
    python run_server.py
    python run_server.py --port 8000 --reload
"""

import sys
import os
import argparse

_root = os.path.dirname(os.path.abspath(__file__))
_src  = os.path.join(_root, "src")
for p in (_root, _src):
    if p not in sys.path:
        sys.path.insert(0, p)

import uvicorn

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host",   default="0.0.0.0")
    parser.add_argument("--port",   default=8000, type=int)
    parser.add_argument("--reload", action="store_true", default=True)
    args = parser.parse_args()

    print(f"[VigilAI] Starting ingestion server on http://{args.host}:{args.port}")
    print(f"[VigilAI] Queue DB: {os.path.join(_root, 'data', 'live_queue.db')}")
    print(f"[VigilAI] Docs:     http://localhost:{args.port}/docs\n")

    uvicorn.run(
        "api_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[_src],
    )
