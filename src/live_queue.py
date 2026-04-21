"""
live_queue.py — Cross-process log queue backed by SQLite.

Both the FastAPI server (port 8000) and the Streamlit dashboard run as
separate OS processes. A module-level Python deque would be invisible across
that boundary. SQLite on disk is the simplest shared store that needs no
extra services (Redis, RabbitMQ, etc.) and is safe under concurrent writes
because SQLite serialises transactions with a file-level lock.

API:
    push(log_dict)          — called by FastAPI middleware
    drain(max_items)        — called by MonitorAgent on each observe cycle
    queue_size()            — called by dashboard for the status badge
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path

# Absolute path so it resolves correctly regardless of CWD or how each
# process imports this module.
_DB_PATH = Path(__file__).resolve().parents[1] / "data" / "live_queue.db"

# One lock per process — SQLite handles cross-process safety via its WAL mode.
_lock = threading.Lock()


def _connect() -> sqlite3.Connection:
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")   # allows concurrent readers + one writer
    conn.execute("PRAGMA synchronous=NORMAL") # fast enough, still crash-safe
    conn.execute("""
        CREATE TABLE IF NOT EXISTS log_queue (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            payload TEXT    NOT NULL
        )
    """)
    conn.commit()
    return conn


def push(log: dict) -> None:
    """Append one log entry. Called by FastAPI middleware (server process)."""
    with _lock:
        conn = _connect()
        conn.execute("INSERT INTO log_queue (payload) VALUES (?)", (json.dumps(log),))
        conn.commit()
        conn.close()


def drain(max_items: int = 5000) -> list[dict]:
    """
    Pop up to max_items logs atomically. Called by MonitorAgent (dashboard process).
    Returns an empty list when the queue is empty — not an error.
    """
    with _lock:
        conn = _connect()
        rows = conn.execute(
            "SELECT id, payload FROM log_queue ORDER BY id LIMIT ?", (max_items,)
        ).fetchall()
        if rows:
            ids = [r[0] for r in rows]
            conn.execute(
                f"DELETE FROM log_queue WHERE id IN ({','.join('?' * len(ids))})", ids
            )
            conn.commit()
        conn.close()
    return [json.loads(r[1]) for r in rows]


def queue_size() -> int:
    """Return the current number of unprocessed log entries."""
    try:
        conn = _connect()
        n = conn.execute("SELECT COUNT(*) FROM log_queue").fetchone()[0]
        conn.close()
        return n
    except Exception:
        return 0
