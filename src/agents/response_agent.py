"""
agents/response_agent.py — Act phase of the agent loop.

Executes decisions (BLOCK / RATE_LIMIT / ALERT / LOG), generates structured
alert dicts, updates long-term memory (feedback loop), and persists results to CSV.
"""

from __future__ import annotations
import time

from alert_system import block_api_key, blocked_keys
from storage      import save_results

_SEVERITY_MAP = {
    "BLOCK":      "CRITICAL",
    "RATE_LIMIT": "WARNING",
    "ALERT":      "INFO",
    "LOG":        "DEBUG",
}


class ResponseAgent:
    """Act: execute decisions, emit alerts, close the feedback loop."""

    def __init__(self, long_term_memory):
        self.ltm    = long_term_memory
        self.alerts: list[dict] = []

    def act(
        self,
        decisions:         list[dict],
        enriched_features: list[dict],
        results_path:      str = "data/results.csv",
    ) -> list[dict]:
        """
        Execute all decisions for one cycle.

        Returns alert dicts for CRITICAL / WARNING / INFO actions.
        LOG-level actions are persisted to CSV but not returned.
        """
        feat_map   = {f["api_key"]: f for f in enriched_features}
        new_alerts = []

        for d in decisions:
            key    = d["api_key"]
            action = d["action"]

            if action == "BLOCK":
                block_api_key(key)

            if action != "LOG":
                new_alerts.append(self._build_alert(d))

            self.ltm.update(key, feat_map.get(key, {}), d["final_label"])

        save_results(decisions, results_path)
        self.alerts = new_alerts
        return new_alerts

    def get_blocked_keys(self) -> list[str]:
        return sorted(blocked_keys)

    def _build_alert(self, d: dict) -> dict:
        return {
            "timestamp":     time.strftime("%Y-%m-%dT%H:%M:%S"),
            "severity":      _SEVERITY_MAP.get(d["action"], "INFO"),
            "api_key":       d["api_key"],
            "action":        d["action"],
            "action_reason": d.get("action_reason", ""),
            "final_label":   d["final_label"],
            "fused_score":   d.get("fused_score", 0.0),
            "confidence":    d.get("confidence", 0.0),
            "risk_score":    d["risk_score"],
            "anomaly_score": d["anomaly_score"],
            "summary":       d.get("summary", ""),
            "reasoning":     d.get("reasoning", ""),
        }
