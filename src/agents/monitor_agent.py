"""
agents/monitor_agent.py — Observe phase of the agent loop.

Generates fresh API logs, extracts per-key features, and enriches each
feature row with signals derived from short-term and long-term memory.
The enriched output gives downstream agents historical context they need
to make confident, memory-informed decisions.
"""

from __future__ import annotations
import simulator
from feature_extractor import extract_features


class MonitorAgent:
    """Observe: ingest logs → extract features → enrich with memory context."""

    def __init__(self, short_term_memory, long_term_memory):
        self.stm = short_term_memory
        self.ltm = long_term_memory

    def observe(
        self,
        n_logs:      int             = 100,
        traffic_mix: dict | None     = None,
    ) -> tuple[list[dict], list[dict]]:
        """
        Run one observation cycle.

        Args:
            n_logs:       Number of log entries to generate.
            traffic_mix:  Optional dict overriding simulator.TRAFFIC_MIX.
                          Keys: normal, brute_force, scraping, ddos (must sum to 1.0).

        Returns:
            (enriched_features, raw_logs)
        """
        raw_logs = self._generate(n_logs, traffic_mix)
        features = extract_features(raw_logs)
        if not features:
            return [], raw_logs
        return [self._enrich(f) for f in features], raw_logs

    # ── Internal ───────────────────────────────────────────────────────────

    def _generate(self, n: int, traffic_mix: dict | None) -> list[dict]:
        """Generate logs, temporarily patching simulator.TRAFFIC_MIX if needed."""
        if traffic_mix is None:
            return simulator.generate_logs(n)
        original = dict(simulator.TRAFFIC_MIX)
        simulator.TRAFFIC_MIX.update(traffic_mix)
        try:
            return simulator.generate_logs(n)
        finally:
            simulator.TRAFFIC_MIX.clear()
            simulator.TRAFFIC_MIX.update(original)

    def _enrich(self, f: dict) -> dict:
        """
        Attach five memory-derived signals to a feature row.

        Added fields:
            request_velocity    — change in average_requests since last window
            historical_avg      — long-term EMA baseline for this key
            baseline_deviation  — % deviation from the key's historical norm
            repeat_offender     — True if key has >= 3 prior HIGH verdicts
            prior_observations  — total cycles this key has been tracked
        """
        key         = f["api_key"]
        current_avg = f["average_requests"]
        baseline    = self.ltm.get_baseline(key)

        # Read velocity before recording so it reflects the previous window
        velocity  = self.stm.velocity(key, "average_requests")
        self.stm.record(key, f)

        return {
            **f,
            "request_velocity":   round(velocity, 2),
            "historical_avg":     round(baseline.get("avg_requests", current_avg), 2),
            "baseline_deviation": round(self.ltm.deviation_from_baseline(key, current_avg), 2),
            "repeat_offender":    self.ltm.is_repeat_offender(key),
            "prior_observations": baseline.get("observations", 0),
        }
