"""
AgentLoop — the single entry point for the VigilAI agentic system.

One call to AgentLoop.run() executes a complete Observe → Reason → Decide → Act
cycle and returns a structured result dict the dashboard can render directly.

Memory is instantiated once and persists across cycles:
  - ShortTermMemory lives in-process (reset on restart)
  - LongTermMemory is persisted to disk and survives restarts

Usage (drop-in for the old run_live_pipeline call in dashboard.py):

    from core.agent_loop import AgentLoop

    loop = AgentLoop()               # create once at module level

    result = loop.run(
        n_logs=100,
        traffic_mix={"normal": 0.6, "brute_force": 0.15,
                     "scraping": 0.15, "ddos": 0.10},
    )
    decisions = result["decisions"]  # list[dict] with reasoning + confidence
    alerts    = result["alerts"]     # list[dict] CRITICAL / WARNING / INFO only
"""

from __future__ import annotations

from memory.short_term      import ShortTermMemory
from memory.long_term       import LongTermMemory
from agents.monitor_agent   import MonitorAgent
from agents.detection_agent import DetectionAgent
from agents.decision_agent  import DecisionAgent
from agents.response_agent  import ResponseAgent


class AgentLoop:
    """
    Orchestrates the four agents across repeated pipeline cycles.
    Instantiate once; call .run() every 3 seconds.
    """

    def __init__(
        self,
        stm_window:    int = 10,
        ltm_path:      str = "data/memory/long_term.json",
        results_path:  str = "data/results.csv",
    ):
        stm = ShortTermMemory(window=stm_window)
        ltm = LongTermMemory(path=ltm_path)

        self._monitor   = MonitorAgent(stm, ltm)
        self._detection = DetectionAgent()
        self._decision  = DecisionAgent()
        self._response  = ResponseAgent(ltm)

        self._results_path = results_path
        self._cycle        = 0

    # ── Public API ─────────────────────────────────────────────────────────

    def run(
        self,
        n_logs:      int             = 100,
        traffic_mix: dict | None     = None,
    ) -> dict:
        """
        Execute one full agent loop cycle.

        Args:
            n_logs:       Number of API log entries to simulate.
            traffic_mix:  Optional traffic distribution override.
                          e.g. {"normal": 0.2, "brute_force": 0.5,
                                "scraping": 0.2, "ddos": 0.1}

        Returns:
            {
                "cycle":     int          — monotonic cycle counter
                "logs":      list[dict]   — raw simulated log entries
                "features":  list[dict]   — enriched per-key feature rows
                "decisions": list[dict]   — full decision records with reasoning
                "alerts":    list[dict]   — CRITICAL/WARNING/INFO alerts only
                "stats":     dict         — quick summary counts for dashboard
            }
        """
        self._cycle += 1

        # ── OBSERVE ────────────────────────────────────────────────────────
        enriched_features, raw_logs = self._monitor.observe(n_logs, traffic_mix)

        if not enriched_features:
            return self._empty_result(raw_logs)

        # ── REASON ─────────────────────────────────────────────────────────
        detections = self._detection.analyze(enriched_features)

        # ── DECIDE ─────────────────────────────────────────────────────────
        decisions = self._decision.decide(detections)

        # ── ACT ────────────────────────────────────────────────────────────
        alerts = self._response.act(decisions, enriched_features, self._results_path)

        return {
            "cycle":     self._cycle,
            "logs":      raw_logs,
            "features":  enriched_features,
            "decisions": decisions,
            "alerts":    alerts,
            "stats":     self._compute_stats(decisions, alerts),
        }

    def blocked_keys(self) -> list[str]:
        """Current firewall block list."""
        return self._response.get_blocked_keys()

    # ── Internal ───────────────────────────────────────────────────────────

    def _compute_stats(self, decisions: list[dict], alerts: list[dict]) -> dict:
        labels = [d["final_label"] for d in decisions]
        return {
            "total_keys":    len(decisions),
            "high":          labels.count("HIGH"),
            "medium":        labels.count("MEDIUM"),
            "low":           labels.count("LOW"),
            "blocked":       len(self._response.get_blocked_keys()),
            "alerts_fired":  len(alerts),
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
