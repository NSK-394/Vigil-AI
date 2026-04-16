import json
import os
import time
from pathlib import Path


_DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "memory" / "long_term.json"


class LongTermMemory:
    """
    Persistent per-key behavioral baseline.

    Survives dashboard restarts. Written to disk after every update so the
    agent accumulates knowledge across sessions — exactly like a SIEM's
    historical context store.

    Schema per key:
        observations      int    — total cycles this key has been seen
        avg_requests      float  — exponential moving average of average_requests
        high_risk_count   int    — cumulative HIGH verdicts
        last_decision     str    — last final_label
        first_seen        float  — unix timestamp of first observation
        last_seen         float  — unix timestamp of most recent update
    """

    def __init__(self, path: str | Path = _DEFAULT_PATH):
        self._path = Path(path)
        self._store: dict[str, dict] = self._load()

    # ── Public API ─────────────────────────────────────────────────────────

    def update(self, api_key: str, features: dict, decision: str) -> None:
        """
        Merge one cycle's observation into this key's long-term record.
        Uses an exponential moving average so recent behavior is weighted more.
        """
        now = time.time()
        rec = self._store.setdefault(api_key, {
            "observations":    0,
            "avg_requests":    0.0,
            "high_risk_count": 0,
            "last_decision":   None,
            "first_seen":      now,
            "last_seen":       now,
        })

        n = rec["observations"]
        avg_req = features.get("average_requests", 0.0)

        # EMA with α = 1/(n+1) so early obs converge fast, later obs are stable
        alpha = 1.0 / (n + 1)
        rec["avg_requests"] = (1 - alpha) * rec["avg_requests"] + alpha * avg_req

        rec["observations"]  += 1
        rec["last_decision"]  = decision
        rec["last_seen"]      = now

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
        How far (in %) the current average_requests deviates from historical norm.
        Returns 0.0 for unseen keys (no baseline yet).
        """
        baseline_avg = self._store.get(api_key, {}).get("avg_requests", 0.0)
        if baseline_avg == 0:
            return 0.0
        return abs(current_avg - baseline_avg) / baseline_avg * 100

    def all_keys(self) -> list[str]:
        return list(self._store.keys())

    def summary(self) -> list[dict]:
        """Flat list of all records — used by dashboard for the key roster."""
        return [{"api_key": k, **v} for k, v in self._store.items()]

    def forget(self, api_key: str) -> None:
        """Remove a key entirely — for testing or manual cleanup."""
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
        with open(self._path, "w") as f:
            json.dump(self._store, f, indent=2)

    def __repr__(self) -> str:
        return f"LongTermMemory(keys={len(self._store)}, path={self._path})"
