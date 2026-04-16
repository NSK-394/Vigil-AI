from collections import defaultdict, deque
import time


class ShortTermMemory:
    """
    Sliding window of recent feature snapshots per API key.

    Tracks the last `window` cycles of behavior for each key.
    Used by DetectionAgent to spot sudden behavioral shifts (velocity spikes).
    """

    def __init__(self, window: int = 10):
        self._window = window
        self._store: dict[str, deque] = defaultdict(lambda: deque(maxlen=window))

    def record(self, api_key: str, features: dict) -> None:
        """Store one cycle's feature snapshot for this key."""
        self._store[api_key].append({**features, "_ts": time.time()})

    def get(self, api_key: str) -> list[dict]:
        """Return the sliding window for this key, oldest first."""
        return list(self._store[api_key])

    def velocity(self, api_key: str, field: str) -> float:
        """
        Rate of change of `field` across the current window.
        Positive = growing, negative = shrinking.
        Returns 0.0 when fewer than 2 observations exist.
        """
        window = self.get(api_key)
        if len(window) < 2:
            return 0.0
        return float(window[-1].get(field, 0) - window[0].get(field, 0))

    def avg(self, api_key: str, field: str) -> float:
        """Rolling average of `field` over the window."""
        window = self.get(api_key)
        if not window:
            return 0.0
        values = [w.get(field, 0) for w in window]
        return sum(values) / len(values)

    def all_keys(self) -> list[str]:
        return list(self._store.keys())

    def clear(self, api_key: str) -> None:
        """Wipe a key's window — used after a confirmed block."""
        self._store.pop(api_key, None)

    def __repr__(self) -> str:
        return f"ShortTermMemory(window={self._window}, keys={len(self._store)})"
