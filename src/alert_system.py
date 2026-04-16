"""
alert_system.py
---------------
Generates human-readable alert messages for high-risk API keys.

Reads the final decision results (from final_decision.py) and fires
a structured alert for every key labelled HIGH.

Each alert includes:
  - severity level
  - api_key
  - risk_score
  - anomaly_score  (if available)
  - recommended action
  - timestamp

Public API:
    generate_alerts(results)  →  list[dict]
"""

import sys
import os
from datetime import datetime

# Force UTF-8 output so emoji in print() don't crash on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


# ══════════════════════════════════════════════════════════════
#  BLOCKING  —  in-memory simulated firewall
# ══════════════════════════════════════════════════════════════

# Persists for the lifetime of the Python process (or Streamlit session).
# In production this would be a Redis set / WAF rule list.
blocked_keys: set = set()


def block_api_key(api_key: str) -> None:
    """
    Add api_key to the simulated block list.
    Logs the action to stdout so you can see it in the terminal.
    """
    if api_key not in blocked_keys:
        blocked_keys.add(api_key)
        print(f"[alert_system] ⛔ BLOCKED: {api_key}")


def unblock_api_key(api_key: str) -> None:
    """Remove a key from the block list (useful for testing)."""
    blocked_keys.discard(api_key)
    print(f"[alert_system] ✅ UNBLOCKED: {api_key}")


def get_blocked_keys() -> list:
    """Return a sorted list of all currently blocked API keys."""
    return sorted(blocked_keys)


# ══════════════════════════════════════════════════════════════
#  CONFIG
# ══════════════════════════════════════════════════════════════

# Labels that trigger alerts. Add "MEDIUM" to also alert on borderline keys.
ALERT_LABELS = {"HIGH"}

# Action recommendation per severity
ACTIONS = {
    "HIGH":   "Rate-limit immediately · trigger CAPTCHA · escalate to SOC L2",
    "MEDIUM": "Monitor closely · set auto-escalation threshold",
    "LOW":    "No action required · continue passive monitoring",
}


# ══════════════════════════════════════════════════════════════
#  HELPER: build one alert dict
# ══════════════════════════════════════════════════════════════

def _build_alert(row: dict) -> dict:
    """
    Convert one result row into a structured alert dictionary.

    Parameters
    ----------
    row : dict
        One entry from the final_decision results list.
        Expected keys: api_key, risk_score, final_label
        Optional key:  anomaly_score

    Returns
    -------
    dict with keys:
        severity, api_key, risk_score, anomaly_score,
        action, timestamp, message
    """
    api_key       = row.get("api_key",       "unknown")
    risk_score    = row.get("risk_score",    0)
    anomaly_score = row.get("anomaly_score", "N/A")   # optional field
    severity      = row.get("final_label",  "HIGH")
    action        = ACTIONS.get(severity, "Review manually")
    timestamp     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Human-readable one-liner shown in logs / dashboards
    message = (
        f"[{severity}] ALERT — api_key '{api_key}' flagged "
        f"(risk_score={risk_score}, anomaly_score={anomaly_score}). "
        f"Action: {action}"
    )

    return {
        "severity":      severity,
        "api_key":       api_key,
        "risk_score":    risk_score,
        "anomaly_score": anomaly_score,
        "action":        action,
        "timestamp":     timestamp,
        "message":       message,
    }


# ══════════════════════════════════════════════════════════════
#  MAIN PUBLIC FUNCTION
# ══════════════════════════════════════════════════════════════

def generate_alerts(results: list) -> list:
    """
    Scan final decision results and generate alerts using the auto response decision engine.
    """
    try:
        from src.decision_engine import take_action
    except ImportError:
        from decision_engine import take_action

    if not results:
        print("[alert_system] ⚠️  No results provided — nothing to scan.")
        return []

    alerts_list = []
    
    # Process every log through the decision engine
    for row in results:
        decision = take_action(row)
        
        # We only escalate HIGH actions (blocks & rate limits) to the live alert dash
        if decision["action"] in ["BLOCK", "RATE_LIMIT"]:
            severity = decision.get("severity", "HIGH")
            if decision["action"] == "BLOCK":
                block_api_key(row.get("api_key", "unknown"))

            alerts_list.append({
                "severity":      severity,
                "api_key":       row.get("api_key", "unknown"),
                "risk_score":    row.get("risk_score", 0),
                "anomaly_score": row.get("anomaly_score", "N/A"),
                "action":        decision["action"],
                "timestamp":     decision["timestamp"],
                "message":       f"[{severity}] Engine response: {decision['message']} (Reason: {decision.get('action_reason', 'N/A')})",
            })

    # Sort — highest risk_score first
    alerts_list.sort(key=lambda a: a["risk_score"], reverse=True)

    if alerts_list:
        print(f"[alert_system] 🚨 {len(alerts_list)} active alert(s) generated via Engine. "
              f"{len(blocked_keys)} key(s) now blocked.")
    else:
        print("[alert_system] ✅ No active alerts — system clear.")

    return alerts_list


# ══════════════════════════════════════════════════════════════
#  QUICK DEMO  —  runs only when executed directly
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Try to run the full pipeline; fall back to hand-crafted data
    try:
        from simulator         import generate_logs
        from feature_extractor import extract_features
        from risk_engine       import calculate_risk
        from detector          import detect_anomalies
        from final_decision    import combine_results

        logs     = generate_logs(400)
        features = extract_features(logs)
        risk     = calculate_risk(features)
        ml       = detect_anomalies(features)
        results  = combine_results(risk, ml)

    except ImportError:
        # Standalone fallback data
        results = [
            {"api_key": "bot_key_001",  "risk_score": 95, "anomaly_score": 97.4, "final_label": "HIGH"},
            {"api_key": "bot_key_002",  "risk_score": 80, "anomaly_score": 88.1, "final_label": "HIGH"},
            {"api_key": "bot_key_003",  "risk_score": 73, "anomaly_score": 79.5, "final_label": "HIGH"},
            {"api_key": "user_key_010", "risk_score": 45, "anomaly_score": 42.0, "final_label": "MEDIUM"},
            {"api_key": "user_key_022", "risk_score": 10, "anomaly_score": 8.1,  "final_label": "LOW"},
        ]

    # ── Run the alert system ──────────────────────────────────────────────
    alerts = generate_alerts(results)

    if not alerts:
        print("No alerts to display.")
    else:
        # Pretty-print each alert
        print(f"\n{'─' * 68}")
        for i, alert in enumerate(alerts, start=1):
            icon = "🔴" if alert["severity"] == "HIGH" else "🟡"
            print(f"\n  {icon}  ALERT #{i}")
            print(f"     API Key       : {alert['api_key']}")
            print(f"     Severity      : {alert['severity']}")
            print(f"     Risk Score    : {alert['risk_score']}")
            print(f"     Anomaly Score : {alert['anomaly_score']}")
            print(f"     Timestamp     : {alert['timestamp']}")
            print(f"     Action        : {alert['action']}")
            print(f"     Message       : {alert['message']}")
        print(f"\n{'─' * 68}")
        print(f"\n  Total alerts fired : {len(alerts)}")