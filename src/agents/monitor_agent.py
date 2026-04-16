"""
MonitorAgent — Observe phase of the agent loop.

Responsibilities:
  1. Generate fresh API logs (via simulator)
  2. Extract per-key behavioral features (via feature_extractor)
  3. Enrich each feature row with short-term + long-term memory context
     so downstream agents see history, not just the current snapshot

Note: simulator.generate_logs() uses a module-level TRAFFIC_MIX global.
We patch it temporarily when the caller supplies a custom mix.
"""

from __future__ import annotations
import simulator
from feature_extractor import extract_features


class MonitorAgent:
    """
    Observe: ingest logs → extract features → enrich with memory.
    Returns (enriched_features, raw_logs).
    """

    def __init__(self, short_term_memory, long_term_memory):
        self.stm = short_term_memory
        self.ltm = long_term_memory

    # ── Public API ─────────────────────────────────────────────────────────

    def observe(
        self,
        n_logs: int = 100,
        traffic_mix: dict | None = None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Run one observation cycle.

        Args:
            n_logs:       Number of log entries to generate this cycle.
            traffic_mix:  Optional dict overriding simulator.TRAFFIC_MIX.
                          e.g. {"normal": 0.2, "brute_force": 0.4,
                                "scraping": 0.2, "ddos": 0.2}
                          Values must sum to 1.0.

        Returns:
            (enriched_features, raw_logs)
        """
        raw_logs = self._generate(n_logs, traffic_mix)
        features = extract_features(raw_logs)

        if not features:
            return [], raw_logs

        enriched = [self._enrich(f) for f in features]
        return enriched, raw_logs

    # ── Internal helpers ───────────────────────────────────────────────────

    def _generate(self, n: int, traffic_mix: dict | None) -> list[dict]:
        """Generate logs, temporarily patching the simulator mix if needed."""
        if traffic_mix is not None:
            original = dict(simulator.TRAFFIC_MIX)
            simulator.TRAFFIC_MIX.update(traffic_mix)
            try:
                logs = simulator.generate_logs(n)
            finally:
                simulator.TRAFFIC_MIX.clear()
                simulator.TRAFFIC_MIX.update(original)
        else:
            logs = simulator.generate_logs(n)
        return logs

    def _enrich(self, f: dict) -> dict:
        """
        Attach memory-derived signals to a feature row.

        Added fields:
            request_velocity   — how fast average_requests changed this window
            historical_avg     — long-term EMA baseline for this key
            baseline_deviation — % deviation from the key's own history
            repeat_offender    — True if key has >= 3 prior HIGH verdicts
            prior_observations — how many cycles this key has been tracked
        """
        key = f["api_key"]
        current_avg = f["average_requests"]

        baseline   = self.ltm.get_baseline(key)
        velocity   = self.stm.velocity(key, "average_requests")
        hist_avg   = baseline.get("avg_requests", current_avg)
        deviation  = self.ltm.deviation_from_baseline(key, current_avg)

        # Record this cycle into the sliding window AFTER reading velocity
        # so velocity reflects the *previous* window, not the current point
        self.stm.record(key, f)

        return {
            **f,
            "request_velocity":   round(velocity, 2),
            "historical_avg":     round(hist_avg, 2),
            "baseline_deviation": round(deviation, 2),
            "repeat_offender":    self.ltm.is_repeat_offender(key),
            "prior_observations": baseline.get("observations", 0),
        }
