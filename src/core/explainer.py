"""
core/explainer.py — Human-readable reasoning traces for agent decisions.

Every verdict produced by DecisionAgent includes a structured explanation
so operators can see exactly why a key was flagged. No black-box decisions.

Output format:
    [LABEL | conf=XX% | fused=YY.Y] — <cause 1>; <cause 2>; ...
"""

from __future__ import annotations

_RULE_HIGH_THRESHOLD    = 70
_RULE_MEDIUM_THRESHOLD  = 40
_ML_ANOMALY_THRESHOLD   = 60
_VELOCITY_THRESHOLD     = 30
_DEVIATION_THRESHOLD    = 50.0


def build_reasoning(
    detection:  dict,
    label:      str,
    fused_score: float,
    confidence:  float,
) -> str:
    """
    Generate a single-line explanation for a verdict.

    Args:
        detection:   Detection dict from DetectionAgent (risk_score,
                     anomaly_score, ml_prediction, request_velocity,
                     repeat_offender, baseline_deviation).
        label:       Final verdict — "HIGH" / "MEDIUM" / "LOW".
        fused_score: Confidence-weighted fusion score (0–100).
        confidence:  Overall agent confidence (0.0–1.0).

    Returns:
        Formatted reasoning string.
    """
    causes = _collect_causes(detection)
    header = f"[{label} | conf={confidence:.0%} | fused={fused_score:.1f}]"
    body   = "; ".join(causes) if causes else "no significant signals — baseline behavior"
    return f"{header} — {body}."


def build_short_summary(detection: dict, label: str) -> str:
    """One-phrase dominant-cause summary for dashboard pills."""
    if detection.get("repeat_offender"):
        return "repeat offender"
    vel = detection.get("request_velocity", 0)
    if vel > _VELOCITY_THRESHOLD:
        return f"velocity spike +{vel:.0f}"
    rs = detection.get("risk_score", 0)
    if rs > _RULE_HIGH_THRESHOLD:
        return f"rule score {rs}"
    ml  = detection.get("ml_prediction", "normal")
    ams = detection.get("anomaly_score", 0)
    if ml == "anomaly" and ams > _ML_ANOMALY_THRESHOLD:
        return f"ML anomaly {ams:.0f}"
    if label == "MEDIUM":
        return "elevated activity"
    return "normal"


def explain_action(action: str, label: str, repeat_offender: bool) -> str:
    """One-line justification for the chosen response action."""
    if action == "BLOCK":
        return (
            "repeat offender auto-escalated to block"
            if repeat_offender
            else "HIGH-risk verdict requires immediate containment"
        )
    reasons = {
        "RATE_LIMIT": "MEDIUM-risk — throttling to limit damage without full block",
        "ALERT":      "MEDIUM-risk — flagged for operator review",
        "LOG":        "LOW-risk — recorded for baseline tracking only",
    }
    return reasons.get(action, f"action={action} for label={label}")


# ── Internal ───────────────────────────────────────────────────────────────

def _collect_causes(d: dict) -> list[str]:
    """Build the ordered list of triggered explanation clauses."""
    causes = []
    rs  = d.get("risk_score", 0)
    ams = d.get("anomaly_score", 0)
    ml  = d.get("ml_prediction", "normal")
    vel = d.get("request_velocity", 0)
    rep = d.get("repeat_offender", False)
    dev = d.get("baseline_deviation", 0.0)

    if rs >= _RULE_HIGH_THRESHOLD:
        causes.append(f"rule engine: high-volume or low-diversity behavior (score {rs})")
    elif rs >= _RULE_MEDIUM_THRESHOLD:
        causes.append(f"rule engine: moderately elevated activity (score {rs})")

    if ml == "anomaly" and ams >= _ML_ANOMALY_THRESHOLD:
        causes.append(f"ML: statistical outlier detected (anomaly score {ams:.1f})")
    elif ml == "anomaly":
        causes.append(f"ML: weak anomaly signal (score {ams:.1f})")

    if vel > _VELOCITY_THRESHOLD:
        causes.append(f"short-term memory: request velocity spike (+{vel:.0f} req/cycle)")
    elif vel < -_VELOCITY_THRESHOLD:
        causes.append(f"short-term memory: sharp traffic drop (-{abs(vel):.0f} req/cycle)")

    if dev >= _DEVIATION_THRESHOLD:
        causes.append(f"long-term memory: {dev:.0f}% above historical baseline")

    if rep:
        causes.append("long-term memory: >=3 prior HIGH verdicts (repeat offender)")

    return causes
