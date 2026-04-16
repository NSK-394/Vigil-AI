"""
Human-readable reasoning traces for every agent decision.

Every verdict produced by DecisionAgent includes a structured explanation
so operators (and interviewers) can see exactly why a key was flagged.
No black-box decisions.

Output format:
    [LABEL | conf=XX% | fused=YY.Y] — <cause 1>; <cause 2>; ...
"""

from __future__ import annotations


# ── Thresholds that trigger individual explanation clauses ─────────────────

_RULE_HIGH_THRESHOLD     = 70    # risk_score that counts as "rule engine flagged"
_RULE_MEDIUM_THRESHOLD   = 40    # risk_score that triggers a softer note
_ML_ANOMALY_THRESHOLD    = 60    # anomaly_score that counts as ML flagged
_VELOCITY_THRESHOLD      = 30    # req/cycle delta that counts as a burst
_DEVIATION_THRESHOLD     = 50.0  # % deviation from historical baseline


def build_reasoning(
    detection: dict,
    label: str,
    fused_score: float,
    confidence: float,
) -> str:
    """
    Generate a single-line human-readable explanation for a verdict.

    Args:
        detection:   Full detection dict from DetectionAgent, expected keys:
                         risk_score, anomaly_score, ml_prediction,
                         request_velocity, repeat_offender,
                         baseline_deviation (optional)
        label:       Final verdict — "HIGH" / "MEDIUM" / "LOW"
        fused_score: Confidence-weighted fusion score (0-100)
        confidence:  Overall confidence in [0.0, 1.0]

    Returns:
        Formatted reasoning string.
    """
    causes = _collect_causes(detection)
    header = f"[{label} | conf={confidence:.0%} | fused={fused_score:.1f}]"

    if not causes:
        body = "no significant signals — baseline behavior"
    else:
        body = "; ".join(causes)

    return f"{header} — {body}."


def build_short_summary(detection: dict, label: str) -> str:
    """
    One-phrase summary for dashboard threat pills and terminal feed lines.
    Much shorter than build_reasoning — single dominant cause only.
    """
    rs  = detection.get("risk_score", 0)
    ams = detection.get("anomaly_score", 0)
    vel = detection.get("request_velocity", 0)
    rep = detection.get("repeat_offender", False)
    ml  = detection.get("ml_prediction", "normal")

    if rep:
        return "repeat offender"
    if vel > _VELOCITY_THRESHOLD:
        return f"velocity spike +{vel:.0f}"
    if rs > _RULE_HIGH_THRESHOLD:
        return f"rule score {rs}"
    if ml == "anomaly" and ams > _ML_ANOMALY_THRESHOLD:
        return f"ML anomaly {ams:.0f}"
    if label == "MEDIUM":
        return "elevated activity"
    return "normal"


def explain_action(action: str, label: str, repeat_offender: bool) -> str:
    """
    One-line justification for the chosen response action.
    Shown in alert cards so operators know why BLOCK vs RATE_LIMIT.
    """
    reasons = {
        "BLOCK": (
            "repeat offender auto-escalated to block"
            if repeat_offender
            else f"HIGH-risk verdict requires immediate containment"
        ),
        "RATE_LIMIT": f"MEDIUM-risk — throttling to limit damage without full block",
        "ALERT":      f"MEDIUM-risk — flagged for operator review",
        "LOG":        f"LOW-risk — recorded for baseline tracking only",
    }
    return reasons.get(action, f"action={action} for label={label}")


# ── Internal helpers ───────────────────────────────────────────────────────

def _collect_causes(d: dict) -> list[str]:
    """Build the ordered list of triggered explanation clauses."""
    causes = []

    rs  = d.get("risk_score", 0)
    ams = d.get("anomaly_score", 0)
    ml  = d.get("ml_prediction", "normal")
    vel = d.get("request_velocity", 0)
    rep = d.get("repeat_offender", False)
    dev = d.get("baseline_deviation", 0.0)

    # Rule engine signal
    if rs >= _RULE_HIGH_THRESHOLD:
        causes.append(
            f"rule engine: high-volume or low-diversity behavior (score {rs})"
        )
    elif rs >= _RULE_MEDIUM_THRESHOLD:
        causes.append(f"rule engine: moderately elevated activity (score {rs})")

    # ML signal
    if ml == "anomaly" and ams >= _ML_ANOMALY_THRESHOLD:
        causes.append(f"ML: statistical outlier detected (anomaly score {ams:.1f})")
    elif ml == "anomaly":
        causes.append(f"ML: weak anomaly signal (score {ams:.1f})")

    # Short-term memory: velocity
    if vel > _VELOCITY_THRESHOLD:
        causes.append(f"short-term memory: request velocity spike (+{vel:.0f} req/cycle)")
    elif vel < -_VELOCITY_THRESHOLD:
        causes.append(f"short-term memory: sharp traffic drop (-{abs(vel):.0f} req/cycle)")

    # Long-term memory: baseline deviation
    if dev >= _DEVIATION_THRESHOLD:
        causes.append(
            f"long-term memory: {dev:.0f}% above historical baseline"
        )

    # Long-term memory: repeat offender flag
    if rep:
        causes.append("long-term memory: >=3 prior HIGH verdicts (repeat offender)")

    return causes
