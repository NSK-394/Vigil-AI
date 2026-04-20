"""
decision_engine.py — Threshold-based action router.

Evaluates each log's risk_score and dispatches the appropriate enforcement
action. Used by the legacy alert_system pipeline; the agentic system routes
actions through agents.decision_agent instead.
"""

import datetime

try:
    import src.actions as actions
except ImportError:
    import actions


def _severity(risk_score: float) -> str:
    if risk_score > 85:
        return actions.CRITICAL
    if risk_score > 70:
        return actions.HIGH
    if risk_score > 50:
        return actions.MEDIUM
    return actions.LOW


def take_action(log: dict) -> dict:
    """
    Evaluate a log entry and return a structured action response.

    Args:
        log: Dict containing at minimum risk_score and api_key.

    Returns:
        Dict with keys: action, action_reason, message,
                        risk_score, severity, timestamp.
    """
    ip         = log.get("ip_address", log.get("ip", "UNKNOWN_IP"))
    api_key    = log.get("api_key", "UNKNOWN_KEY")
    risk_score = float(log.get("risk_score", 0))
    severity   = _severity(risk_score)
    timestamp  = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    response = {
        "action":        "",
        "action_reason": "",
        "message":       "",
        "risk_score":    risk_score,
        "severity":      severity,
        "timestamp":     timestamp,
    }

    if risk_score > 80:
        response.update({
            "action":        "BLOCK",
            "message":       f"Key {api_key} blocked (risk: {risk_score}).",
            "action_reason": "Risk score exceeds 80 — immediate network-level block.",
        })
        actions.block_ip(ip, api_key, risk_score)

    elif risk_score > 50:
        response.update({
            "action":        "RATE_LIMIT",
            "message":       f"Key {api_key} rate-limited (risk: {risk_score}).",
            "action_reason": "Risk score exceeds 50 — traffic throttled.",
        })
        actions.rate_limit(api_key, risk_score)

    else:
        response.update({
            "action":        "ALLOW",
            "message":       f"Traffic allowed (risk: {risk_score}).",
            "action_reason": "Risk score within normal threshold.",
        })
        actions.mark_normal(api_key)

    return response


def process_batch(logs: list[dict]) -> list[dict]:
    """Apply take_action to each log and return augmented records."""
    for log in logs:
        log.update(take_action(log))
    return logs
