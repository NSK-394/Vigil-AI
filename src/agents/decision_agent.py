"""
agents/decision_agent.py — Decide phase of the agent loop.

Fuses rule-engine and ML signals via confidence-weighted blending, selects
the highest-priority action, and attaches a full reasoning trace to every verdict.

Action priority: BLOCK > RATE_LIMIT > ALERT > LOG
"""

from __future__ import annotations
from core.confidence import weighted_fusion, label_from_score
from core.explainer  import build_reasoning, build_short_summary, explain_action

_VELOCITY_BOOST_THRESHOLD  = 30
_DEVIATION_BOOST_THRESHOLD = 60.0
_VELOCITY_BOOST            = 12
_DEVIATION_BOOST           = 10
_REPEAT_BOOST              = 18


class DecisionAgent:
    """Decide: fuse signals → verdict → action → reasoning trace."""

    def decide(self, detections: list[dict]) -> list[dict]:
        """
        Produce a final decision for every detection dict.

        Adds to each record: final_label, fused_score, confidence,
        action, action_reason, reasoning, summary.
        Returns decisions sorted HIGH-first, then by confidence desc.
        """
        decisions = []
        for d in detections:
            label, fused, conf = self._fuse(d)
            action             = self._select_action(label, d)
            decisions.append({
                **d,
                "final_label":   label,
                "fused_score":   fused,
                "confidence":    conf,
                "action":        action,
                "action_reason": explain_action(action, label, d["repeat_offender"]),
                "reasoning":     build_reasoning(d, label, fused, conf),
                "summary":       build_short_summary(d, label),
            })

        decisions.sort(
            key=lambda x: (
                x["final_label"] == "HIGH",
                x["final_label"] == "MEDIUM",
                x["confidence"],
                x["fused_score"],
            ),
            reverse=True,
        )
        return decisions

    def _fuse(self, d: dict) -> tuple[str, float, float]:
        vel_boost = _VELOCITY_BOOST  if d["request_velocity"]   > _VELOCITY_BOOST_THRESHOLD  else 0
        dev_boost = _DEVIATION_BOOST if d["baseline_deviation"]  > _DEVIATION_BOOST_THRESHOLD else 0
        rep_boost = _REPEAT_BOOST    if d["repeat_offender"]                                  else 0

        fused, conf = weighted_fusion(
            rule_score     = d["risk_score"],
            ml_score       = d["anomaly_score"],
            rule_conf      = d["rule_confidence"],
            ml_conf        = d["ml_confidence"],
            velocity_boost = vel_boost,
            repeat_boost   = rep_boost + dev_boost,
        )
        return label_from_score(fused), fused, conf

    def _select_action(self, label: str, d: dict) -> str:
        if label == "HIGH":
            return "BLOCK"
        if label == "MEDIUM":
            return "BLOCK" if d["repeat_offender"] else "RATE_LIMIT"
        if d["ml_prediction"] == "anomaly" or d["request_velocity"] > _VELOCITY_BOOST_THRESHOLD:
            return "ALERT"
        return "LOG"
