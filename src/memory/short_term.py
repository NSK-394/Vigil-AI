"""
memory/short_term.py — Sliding-window behavioral memory per API key.

Tracks the last `window` feature snapshots for each key so DetectionAgent
can compute velocity (rate of change) and rolling averages across cycles.
"""

from collections import defaultdict, deque
import time


class ShortTermMemory:
    """Sliding window of recent feature snapshots per API key."""

    def __init__(self, window: int = 10):
        self._window = window
        self._store: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))

    def record(self, api_key: str, features: dict) -> None:
        """Append one cycle's feature snapshot for this key."""
        self._store[api_key].append({**features, "_ts": time.time()})

    def get(self, api_key: str) -> list[dict]:
        """Return the sliding window for this key, oldest first."""
        return list(self._store[api_key])

    def velocity(self, api_key: str, field: str) -> float:
        """
        Rate of change of `field` across the window.
        Positive = growing, negative = shrinking, 0.0 = fewer than 2 observations.
        """
        window = self.get(api_key)
        if len(window) < 2:
            return 0.0
        return float(window[-1].get(field, 0) - window[0].get(field, 0))

    def avg(self, api_key: str, field: str) -> float:
        """Rolling average of `field` over the current window."""
        window = self.get(api_key)
        if not window:
            return 0.0
        return sum(w.get(field, 0) for w in window) / len(window)

    def all_keys(self) -> list[str]:
        return list(self._store.keys())

    def clear(self, api_key: str) -> None:
        """Evict a key's window — used after a confirmed block."""
        self._store.pop(api_key, None)

    def __repr__(self) -> str:
        return f"ShortTermMemory(window={self._window}, keys={len(self._store)})"
