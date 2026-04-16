"""
ResponseAgent — Act phase of the agent loop.

Responsibilities:
  1. Execute the action chosen by DecisionAgent (BLOCK / RATE_LIMIT / ALERT / LOG)
  2. Generate structured alert dicts for the dashboard
  3. Feed the outcome back into long-term memory (the feedback loop)
  4. Persist results to CSV via storage.py

The feedback loop is the key agentic upgrade: after acting, the agent
updates each key's long-term behavioral baseline. Over time, this lets
the system recognize repeat offenders without any manual configuration.
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
    """
    Act: execute decisions, generate alerts, close the feedback loop.
    """

    def __init__(self, long_term_memory):
        self.ltm = long_term_memory
        self.alerts: list[dict] = []

    # ── Public API ─────────────────────────────────────────────────────────

    def act(
        self,
        decisions:         list[dict],
        enriched_features: list[dict],
        results_path:      str = "data/results.csv",
    ) -> list[dict]:
        """
        Execute all decisions for one agent loop cycle.

        Args:
            decisions:         Output of DecisionAgent.decide().
            enriched_features: Output of MonitorAgent.observe() — needed
                               for the feedback loop's feature snapshot.
            results_path:      CSV file to persist results into.

        Returns:
            List of alert dicts for this cycle (CRITICAL / WARNING / INFO).
            LOG-level actions are silently written to CSV and not returned.
        """
        feat_map   = {f["api_key"]: f for f in enriched_features}
        new_alerts = []

        for d in decisions:
            key    = d["api_key"]
            action = d["action"]

            # ── Execute action ─────────────────────────────────────────────
            if action == "BLOCK":
                block_api_key(key)

            # ── Build alert (all actions except LOG get a record) ──────────
            if action != "LOG":
                new_alerts.append(self._build_alert(d))

            # ── Feedback loop: update long-term memory ─────────────────────
            feat = feat_map.get(key, {})
            self.ltm.update(key, feat, d["final_label"])

        # ── Persist to CSV (full decision set including LOG rows) ──────────
        save_results(decisions, results_path)

        self.alerts = new_alerts
        return new_alerts

    def get_blocked_keys(self) -> list[str]:
        """Return the current in-memory firewall block list."""
        return sorted(blocked_keys)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _build_alert(self, d: dict) -> dict:
        """
        Build a structured alert dict from a decision.
        Includes the full reasoning trace so operators can see exactly
        why the action was taken — no black-box alerts.
        """
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
