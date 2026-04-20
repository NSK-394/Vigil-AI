"""
alert_system.py — Alert generation and in-memory WAF block list.

Provides the simulated firewall state (blocked_keys) shared across
the pipeline, plus generate_alerts() for the legacy pipeline path.
The agentic system calls block_api_key() directly via ResponseAgent.
"""

from datetime import datetime

# In-memory firewall block list — persists for the lifetime of the process.
# In production this would be a Redis set or WAF rule store.
blocked_keys: set[str] = set()


def block_api_key(api_key: str) -> None:
    """Add api_key to the simulated block list."""
    if api_key not in blocked_keys:
        blocked_keys.add(api_key)
        print(f"[alert_system] BLOCKED: {api_key}")


def unblock_api_key(api_key: str) -> None:
    """Remove api_key from the block list."""
    blocked_keys.discard(api_key)


def get_blocked_keys() -> list[str]:
    """Return a sorted list of all currently blocked API keys."""
    return sorted(blocked_keys)


# ── Action labels used by the legacy pipeline ──────────────────────────────
_ACTIONS = {
    "HIGH":   "Rate-limit immediately · trigger CAPTCHA · escalate to SOC L2",
    "MEDIUM": "Monitor closely · set auto-escalation threshold",
    "LOW":    "No action required · continue passive monitoring",
}


def generate_alerts(results: list[dict]) -> list[dict]:
    """
    Process final decision results through the legacy decision engine
    and return structured alerts for BLOCK and RATE_LIMIT actions.

    Args:
        results: List of verdict dicts (api_key, risk_score, final_label, ...).

    Returns:
        List of alert dicts sorted by risk_score descending.
    """
    try:
        from src.decision_engine import take_action
    except ImportError:
        from decision_engine import take_action

    if not results:
        return []

    alerts = []
    for row in results:
        decision = take_action(row)
        if decision["action"] in ("BLOCK", "RATE_LIMIT"):
            if decision["action"] == "BLOCK":
                block_api_key(row.get("api_key", "unknown"))
            alerts.append({
                "severity":      decision.get("severity", "HIGH"),
                "api_key":       row.get("api_key", "unknown"),
                "risk_score":    row.get("risk_score", 0),
                "anomaly_score": row.get("anomaly_score", "N/A"),
                "action":        decision["action"],
                "timestamp":     decision["timestamp"],
                "message": (
                    f"[{decision.get('severity', 'HIGH')}] "
                    f"{decision['message']} "
                    f"(Reason: {decision.get('action_reason', 'N/A')})"
                ),
            })

    alerts.sort(key=lambda a: a["risk_score"], reverse=True)
    return alerts
