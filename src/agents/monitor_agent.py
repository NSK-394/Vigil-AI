"""
agents/monitor_agent.py — Observe phase of the agent loop.

Supports two data sources:
    "simulated" — generate synthetic logs via simulator (default, demo mode)
    "real"      — drain real request logs from the shared SQLite queue
                  written by the FastAPI server (api_server.py / live_queue.py)

Both paths produce identically-shaped log dicts so feature_extractor and all
downstream agents are completely unaware of the source.
"""

from __future__ import annotations
import simulator
from feature_extractor import extract_features


class MonitorAgent:
    """Observe: ingest logs → extract features → enrich with memory context."""

    def __init__(self, short_term_memory, long_term_memory):
        self.stm = short_term_memory
        self.ltm = long_term_memory

    # ── Public API ─────────────────────────────────────────────────────────

    def observe(
        self,
        n_logs:      int         = 100,
        traffic_mix: dict | None = None,
        source:      str         = "simulated",
    ) -> tuple[list[dict], list[dict]]:
        """
        Run one observation cycle.

        Args:
            n_logs:       Max logs to consume (simulated: exact; real: upper bound).
            traffic_mix:  Simulator traffic-mix override (simulated source only).
            source:       "simulated" or "real".

        Returns:
            (enriched_features, raw_logs)
        """
        raw_logs = (
            self._generate_real(n_logs)
            if source == "real"
            else self._generate_simulated(n_logs, traffic_mix)
        )

        features = extract_features(raw_logs)
        if not features:
            return [], raw_logs
        return [self._enrich(f) for f in features], raw_logs

    def ingest_log(self, log_dict: dict) -> None:
        """
        Push a single log dict into the shared SQLite queue.
        Useful for tests, webhooks, or external integrations.
        """
        from live_queue import push
        push(log_dict)

    # ── Internal ───────────────────────────────────────────────────────────

    def _generate_simulated(self, n: int, traffic_mix: dict | None) -> list[dict]:
        """Generate synthetic logs, temporarily patching simulator.TRAFFIC_MIX if needed."""
        if traffic_mix is None:
            return simulator.generate_logs(n)
        original = dict(simulator.TRAFFIC_MIX)
        simulator.TRAFFIC_MIX.update(traffic_mix)
        try:
            return simulator.generate_logs(n)
        finally:
            simulator.TRAFFIC_MIX.clear()
            simulator.TRAFFIC_MIX.update(original)

    def _generate_real(self, max_logs: int) -> list[dict]:
        """
        Drain up to max_logs entries from the shared SQLite queue.
        Returns an empty list when the queue has no pending entries — not an error.
        The caller's extract_features() will return nothing and the agent loop
        will emit an empty-result dict, which the dashboard handles gracefully.
        """
        from live_queue import drain
        return drain(max_logs)

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
        velocity = self.stm.velocity(key, "average_requests")
        self.stm.record(key, f)

        return {
            **f,
            "request_velocity":   round(velocity, 2),
            "historical_avg":     round(baseline.get("avg_requests", current_avg), 2),
            "baseline_deviation": round(self.ltm.deviation_from_baseline(key, current_avg), 2),
            "repeat_offender":    self.ltm.is_repeat_offender(key),
            "prior_observations": baseline.get("observations", 0),
        }
