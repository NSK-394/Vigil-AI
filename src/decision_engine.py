import datetime
try:
    import src.actions as actions
except ImportError:
    import actions

def calculate_severity(risk_score: float) -> str:
    """
    Maps a risk score (0-100) to a standardized severity band.
      LOW      -> risk <= 50
      MEDIUM   -> 51-70
      HIGH     -> 71-85
      CRITICAL -> >85
    """
    if risk_score > 85:
        return actions.CRITICAL
    elif risk_score > 70:
        return actions.HIGH
    elif risk_score > 50:
        return actions.MEDIUM
    else:
        return actions.LOW

def take_action(log: dict) -> dict:
    """
    Evaluates an incoming log and decides the appropriate automated response,
    mapping severity levels and executing mitigation actions.
    
    Args:
        log (dict): A log entry containing at minimum risk_score and api_key.
        
    Returns:
        dict: A fully structured execution detail map determining the response.
    """
    ip = log.get("ip_address", log.get("ip", "UNKNOWN_IP"))
    api_key = log.get("api_key", "UNKNOWN_KEY")
    risk_score = float(log.get("risk_score", 0))
    
    severity = calculate_severity(risk_score)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    response = {
        "action": "",
        "action_reason": "",
        "message": "",
        "risk_score": risk_score,
        "severity": severity,
        "timestamp": timestamp
    }

    # Action routing based purely on specified thresholds
    if risk_score > 80:
        response["action"] = "BLOCK"
        response["message"] = f"Key {api_key} blocked (Risk: {risk_score})."
        response["action_reason"] = "Risk score exceeds 80; triggered immediate network-level block."
        
        actions.block_ip(ip, api_key, risk_score)
        
    elif risk_score > 50:
        response["action"] = "RATE_LIMIT"
        response["message"] = f"API Key {api_key} rate limited (Risk: {risk_score})."
        response["action_reason"] = "Risk score exceeds 50; traffic throttled to mitigate potential abuse."
        
        actions.rate_limit(api_key, risk_score)
        
    else:
        response["action"] = "ALLOW"
        response["message"] = f"Traffic allowed (Risk: {risk_score})."
        response["action_reason"] = "Risk score within normal threshold; traffic cleared organically."
        
        actions.mark_normal(api_key)
        
    return response

def process_batch(logs: list) -> list:
    """
    Pipeline Integration: Iterates through a continuous stream or batch of logs,
    applies the decision engine, and updates the logs linearly.
    """
    updated_logs = []
    
    for log in logs:
        # 1. Take action and generate the decision block
        result = take_action(log)
        
        # 2. Update the original log directly with the response fields
        log.update(result)
        
        # 3. Store the fully augmented log for downstream dashboard visualization
        updated_logs.append(log)
        
    return updated_logs
