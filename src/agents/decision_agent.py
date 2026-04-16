"""
DecisionAgent — Decide phase of the agent loop.

Fuses rule-engine and ML signals using confidence-weighted blending,
then selects the highest-priority action and generates a full reasoning
trace for every verdict.

This replaces the original final_decision.py hard-threshold fusion with
a more agent-like approach: the system knows how confident it is, can
escalate repeat offenders, and explains every decision in plain language.

Action priority ladder (highest → lowest):
    BLOCK       — immediate containment, HIGH risk or repeat offender
    RATE_LIMIT  — traffic throttle, MEDIUM risk
    ALERT       — flag for human review, borderline
    LOG         — passive record, LOW risk
"""

from __future__ import annotations
from core.confidence import weighted_fusion, label_from_score, compute_confidence
from core.explainer  import build_reasoning, build_short_summary, explain_action


# Velocity and baseline deviation thresholds that trigger score boosts
_VELOCITY_BOOST_THRESHOLD  = 30    # req/cycle delta → +12 to fused score
_DEVIATION_BOOST_THRESHOLD = 60.0  # % above baseline  → +10 to fused score
_VELOCITY_BOOST            = 12
_DEVIATION_BOOST           = 10
_REPEAT_BOOST              = 18


class DecisionAgent:
    """
    Decide: fuse signals → verdict → action → reasoning trace.
    """

    # ── Public API ─────────────────────────────────────────────────────────

    def decide(self, detections: list[dict]) -> list[dict]:
        """
        Produce a final decision for every detection.

        Args:
            detections: Output of DetectionAgent.analyze().

        Returns:
            List of decision dicts, HIGH-confidence threats first.
            Each dict adds to the detection:
                final_label  — "HIGH" / "MEDIUM" / "LOW"
                fused_score  — confidence-weighted combined score (0-100)
                confidence   — overall agent confidence (0.0-1.0)
                action       — "BLOCK" / "RATE_LIMIT" / "ALERT" / "LOG"
                action_reason — one-line justification for the chosen action
                reasoning    — full multi-signal explanation string
                summary      — one-phrase short summary for dashboard pills
        """
        decisions = []
        for d in detections:
            label, fused, conf = self._fuse(d)
            action             = self._select_action(label, d)
            reasoning          = build_reasoning(d, label, fused, conf)
            summary            = build_short_summary(d, label)
            action_reason      = explain_action(action, label, d["repeat_offender"])

            decisions.append({
                **d,
                "final_label":   label,
                "fused_score":   fused,
                "confidence":    conf,
                "action":        action,
                "action_reason": action_reason,
                "reasoning":     reasoning,
                "summary":       summary,
            })

        # Sort: HIGH first, then by confidence desc, then fused_score desc
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

    # ── Internal helpers ───────────────────────────────────────────────────

    def _fuse(self, d: dict) -> tuple[str, float, float]:
        """
        Confidence-weighted fusion of rule + ML scores with memory boosts.
        Returns (label, fused_score, confidence).
        """
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

        label = label_from_score(fused)
        return label, fused, conf

    def _select_action(self, label: str, d: dict) -> str:
        """
        Choose the highest-priority action for this verdict.

        Escalation rules (applied in order):
          1. Repeat offender on MEDIUM → escalate to BLOCK
          2. HIGH                       → BLOCK
          3. MEDIUM, high velocity      → RATE_LIMIT (already chosen)
          4. MEDIUM                     → RATE_LIMIT
          5. LOW, with any anomaly      → ALERT
          6. LOW, clean                 → LOG
        """
        if label == "HIGH":
            return "BLOCK"

        if label == "MEDIUM":
            # Repeat offenders don't get a second chance at MEDIUM
            if d["repeat_offender"]:
                return "BLOCK"
            return "RATE_LIMIT"

        # LOW
        if d["ml_prediction"] == "anomaly" or d["request_velocity"] > _VELOCITY_BOOST_THRESHOLD:
            return "ALERT"
        return "LOG"
