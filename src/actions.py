"""
actions.py — Simulated WAF / firewall enforcement actions.

Each function represents a response primitive that would map to a real
enforcement layer (AWS WAF rule, Nginx rate-limit, PagerDuty alert, etc.)
in a production deployment. Here they produce structured terminal output.
"""

import datetime

# Severity level constants
LOW      = "LOW"
MEDIUM   = "MEDIUM"
HIGH     = "HIGH"
CRITICAL = "CRITICAL"


def _log(level: str, message: str) -> None:
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{level}] {ts} | {message}")


def block_ip(ip: str, api_key: str, risk_score: float | None = None) -> None:
    """Simulate a hard block at the firewall/WAF layer."""
    score_str = f" (score: {risk_score})" if risk_score is not None else ""
    origin    = f"IP {ip} / " if ip and ip != "UNKNOWN_IP" else ""
    _log(CRITICAL, f"Blocked {origin}Key {api_key} — extreme risk{score_str}")


def rate_limit(api_key: str, risk_score: float | None = None) -> None:
    """Simulate dynamic rate limiting on a suspicious key."""
    score_str = f" (score: {risk_score})" if risk_score is not None else ""
    _log(HIGH, f"Rate-limited Key {api_key} — suspicious activity{score_str}")


def send_alert(message: str, severity: str = MEDIUM) -> None:
    """Simulate dispatching an alert to SOC / escalation channels."""
    _log(severity, f"ALERT → {message}")


def mark_normal(api_key: str) -> None:
    """Simulate clearing traffic through the security pipeline."""
    _log(LOW, f"Traffic cleared for Key {api_key}")
