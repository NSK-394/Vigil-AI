"""
memory/long_term.py — Persistent per-key behavioral baseline.

Survives dashboard restarts. Stores a rolling EMA of each key's
average_requests, cumulative HIGH verdicts, and observation history.
The agent uses this to detect repeat offenders and baseline deviations.
"""

import json
import os
import time
from pathlib import Path

_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "memory" / "long_term.json"


class LongTermMemory:
    """
    Persistent behavioral baseline store, backed by a JSON file.

    Schema per key:
        observations      int   — total cycles observed
        avg_requests      float — EMA of average_requests (α = 1/n)
        high_risk_count   int   — cumulative HIGH verdicts
        last_decision     str   — most recent final_label
        first_seen        float — unix timestamp of first observation
        last_seen         float — unix timestamp of latest update
    """

    def __init__(self, path: str | Path = _DEFAULT_PATH):
        self._path  = Path(path)
        self._store = self._load()

    # ── Public API ─────────────────────────────────────────────────────────

    def update(self, api_key: str, features: dict, decision: str) -> None:
        """Merge one cycle's observation into this key's long-term record."""
        now = time.time()
        rec = self._store.setdefault(api_key, {
            "observations":    0,
            "avg_requests":    0.0,
            "high_risk_count": 0,
            "last_decision":   None,
            "first_seen":      now,
            "last_seen":       now,
        })
        n     = rec["observations"]
        alpha = 1.0 / (n + 1)
        rec["avg_requests"]    = (1 - alpha) * rec["avg_requests"] + alpha * features.get("average_requests", 0.0)
        rec["observations"]   += 1
        rec["last_decision"]   = decision
        rec["last_seen"]       = now
        if decision == "HIGH":
            rec["high_risk_count"] += 1
        self._save()

    def get_baseline(self, api_key: str) -> dict:
        """Return the full stored record for a key, or {} if unseen."""
        return self._store.get(api_key, {})

    def is_repeat_offender(self, api_key: str, threshold: int = 3) -> bool:
        """True if this key has accumulated >= threshold HIGH verdicts."""
        return self._store.get(api_key, {}).get("high_risk_count", 0) >= threshold

    def deviation_from_baseline(self, api_key: str, current_avg: float) -> float:
        """
        Percentage deviation of current_avg from the key's historical EMA.
        Returns 0.0 for unseen keys.
        """
        baseline = self._store.get(api_key, {}).get("avg_requests", 0.0)
        if baseline == 0:
            return 0.0
        return abs(current_avg - baseline) / baseline * 100

    def all_keys(self) -> list[str]:
        return list(self._store.keys())

    def summary(self) -> list[dict]:
        """Flat list of all records — used by the dashboard roster."""
        return [{"api_key": k, **v} for k, v in self._store.items()]

    def forget(self, api_key: str) -> None:
        """Remove a key entirely."""
        self._store.pop(api_key, None)
        self._save()

    # ── Internal ───────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self._path.exists():
            try:
                with open(self._path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {}
        return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(self._store, f, indent=2)
        os.replace(tmp, self._path)

    def __repr__(self) -> str:
        return f"LongTermMemory(keys={len(self._store)}, path={self._path})"
