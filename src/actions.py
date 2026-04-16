import datetime

# Severity Levels Constants
LOW = "LOW"
MEDIUM = "MEDIUM"
HIGH = "HIGH"
CRITICAL = "CRITICAL"

def log_action(level: str, message: str) -> None:
    """
    Shared helper function to format and print logs in a professional SOC style.
    Maintains a consistent hacker terminal vibe across the pipeline.
    """
    current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted_log = f"[{level}] {current_time} | {message}"
    print(formatted_log)

def block_ip(ip: str, api_key: str, risk_score: float = None) -> None:
    """
    Simulates applying a hard block at the firewall/WAF layer.
    Alerts the system that traffic from this origin has been dropped entirely.
    """
    score_str = f" (score: {risk_score})" if risk_score is not None else ""
    ip_str = f"IP {ip} / " if ip and ip != "UNKNOWN_IP" else ""
    
    log_action(CRITICAL, f"Blocked {ip_str}Key {api_key} due to extreme risk threshold{score_str}")

def rate_limit(api_key: str, risk_score: float = None) -> None:
    """
    Simulates applying a dynamic rate limit to a suspicious endpoint or key.
    Allows traffic but severely restricts frequency to mitigate abuse.
    """
    score_str = f" (score: {risk_score})" if risk_score is not None else ""
    log_action(HIGH, f"Throttled API Key {api_key}. Rate limit applied due to suspicious behavior{score_str}")

def send_alert(message: str, severity: str = MEDIUM) -> None:
    """
    Simulates sending an alert to the SOC dashboard or escalation channels.
    """
    log_action(severity, f"ALERT NOTIFICATION -> {message}")

def mark_normal(api_key: str) -> None:
    """
    Simulates successfully clearing traffic through the security pipeline.
    """
    log_action(LOW, f"Traffic cleared for Key {api_key}. Processed normally.")
