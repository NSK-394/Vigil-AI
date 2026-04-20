"""
agents/core/agent_loop.py — Orchestrates the four-agent Observe → Reason → Decide → Act cycle.

Instantiate once (e.g., in st.session_state); call .run() each cycle.
ShortTermMemory is in-process; LongTermMemory persists to disk across restarts.
"""

from __future__ import annotations

from memory.short_term      import ShortTermMemory
from memory.long_term       import LongTermMemory
from agents.monitor_agent   import MonitorAgent
from agents.detection_agent import DetectionAgent
from agents.decision_agent  import DecisionAgent
from agents.response_agent  import ResponseAgent


class AgentLoop:
    """Single entry point for one complete VigilAI pipeline cycle."""

    def __init__(
        self,
        stm_window:   int = 10,
        ltm_path:     str = "data/memory/long_term.json",
        results_path: str = "data/results.csv",
    ):
        stm = ShortTermMemory(window=stm_window)
        ltm = LongTermMemory(path=ltm_path)

        self._monitor      = MonitorAgent(stm, ltm)
        self._detection    = DetectionAgent()
        self._decision     = DecisionAgent()
        self._response     = ResponseAgent(ltm)
        self._results_path = results_path
        self._cycle        = 0

    def run(
        self,
        n_logs:      int          = 100,
        traffic_mix: dict | None  = None,
        source:      str          = "simulated",
    ) -> dict:
        """
        Execute one full cycle and return a result dict with keys:
            cycle, logs, features, decisions, alerts, stats

        Args:
            source: "simulated" (default) or "real" (drains api_server buffer).
        """
        self._cycle += 1

        enriched_features, raw_logs = self._monitor.observe(n_logs, traffic_mix, source)
        if not enriched_features:
            return self._empty_result(raw_logs)

        detections = self._detection.analyze(enriched_features)
        decisions  = self._decision.decide(detections)
        alerts     = self._response.act(decisions, enriched_features, self._results_path)

        return {
            "cycle":     self._cycle,
            "logs":      raw_logs,
            "features":  enriched_features,
            "decisions": decisions,
            "alerts":    alerts,
            "stats":     self._compute_stats(decisions, alerts),
        }

    def blocked_keys(self) -> list[str]:
        return self._response.get_blocked_keys()

    def _compute_stats(self, decisions: list[dict], alerts: list[dict]) -> dict:
        labels = [d["final_label"] for d in decisions]
        return {
            "total_keys":     len(decisions),
            "high":           labels.count("HIGH"),
            "medium":         labels.count("MEDIUM"),
            "low":            labels.count("LOW"),
            "blocked":        len(self._response.get_blocked_keys()),
            "alerts_fired":   len(alerts),
            "avg_confidence": round(
                sum(d["confidence"] for d in decisions) / len(decisions), 3
            ) if decisions else 0.0,
        }

    def _empty_result(self, raw_logs: list) -> dict:
        return {
            "cycle":     self._cycle,
            "logs":      raw_logs,
            "features":  [],
            "decisions": [],
            "alerts":    [],
            "stats":     {"total_keys": 0, "high": 0, "medium": 0,
                          "low": 0, "blocked": 0, "alerts_fired": 0,
                          "avg_confidence": 0.0},
        }
