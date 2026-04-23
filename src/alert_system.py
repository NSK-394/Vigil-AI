"""
alert_system.py — Alert generation and in-memory WAF block list.

Provides the simulated firewall state (blocked_keys) shared across
the pipeline, plus generate_alerts() for the legacy pipeline path.
The agentic system calls block_api_key() directly via ResponseAgent.

External alerting (Slack, email) is triggered by ResponseAgent on BLOCK actions.
Credentials are read from environment variables; missing vars are silently ignored.
"""

import os
import smtplib
import threading
from datetime import datetime, timezone
from email.mime.text import MIMEText

import httpx

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

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


def send_slack_alert(verdict: str, api_key: str, reasoning: str) -> None:
    """
    Fire-and-forget Slack alert via incoming webhook.
    Silently no-ops when SLACK_WEBHOOK_URL is not set.
    Runs in a daemon thread — never blocks or crashes the agent pipeline.
    """
    def _post() -> None:
        webhook = os.environ.get("SLACK_WEBHOOK_URL", "")
        if not webhook:
            return
        payload = {
            "text": (
                f"🚨 VigilAI Alert\n"
                f"Key: {api_key}\n"
                f"Verdict: {verdict}\n"
                f"Reason: {reasoning}"
            )
        }
        try:
            resp = httpx.post(webhook, json=payload, timeout=5.0)
            print(f"[alert_system] Slack alert sent — HTTP {resp.status_code}")
        except Exception as exc:
            print(f"[alert_system] Slack alert failed: {exc}")

    threading.Thread(target=_post, daemon=True).start()


def send_email_alert(verdict: str, api_key: str, reasoning: str) -> None:
    """
    Fire-and-forget email alert via Gmail SMTP.
    Silently no-ops when GMAIL_ADDRESS or GMAIL_APP_PASSWORD are not set.
    Requires a Gmail App Password (2FA must be enabled on the account).
    Runs in a daemon thread — never blocks or crashes the agent pipeline.
    """
    def _send() -> None:
        addr     = os.environ.get("GMAIL_ADDRESS", "")
        password = os.environ.get("GMAIL_APP_PASSWORD", "")
        if not addr or not password:
            return

        now  = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        body = (
            f"VigilAI Security Alert\n"
            f"======================\n"
            f"API Key : {api_key}\n"
            f"Verdict : {verdict}\n"
            f"Reason  : {reasoning}\n"
            f"Time    : {now}\n"
        )
        msg            = MIMEText(body, "plain")
        msg["Subject"] = f"VigilAI Alert — {verdict} detected"
        msg["From"]    = addr
        msg["To"]      = addr

        try:
            with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
                smtp.ehlo()
                smtp.starttls()
                smtp.login(addr, password)
                smtp.sendmail(addr, addr, msg.as_string())
            print(f"[alert_system] Email alert sent to {addr}")
        except Exception as exc:
            print(f"[alert_system] Email alert failed: {exc}")

    threading.Thread(target=_send, daemon=True).start()


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
