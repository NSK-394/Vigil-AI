"""
final_decision.py — Rule + ML verdict fusion layer.

Merges risk_engine and detector outputs into one final label per api_key.
Used by the legacy pipeline; the agentic system uses core.confidence instead.
"""

RISK_HIGH_THRESHOLD   = 70
RISK_MEDIUM_THRESHOLD = 30


def _decide(risk_score: float, prediction: str) -> str:
    if risk_score > RISK_HIGH_THRESHOLD or prediction == "anomaly":
        return "HIGH"
    if risk_score > RISK_MEDIUM_THRESHOLD:
        return "MEDIUM"
    return "LOW"


def combine_results(risk_results: list[dict], ml_results: list[dict]) -> list[dict]:
    """
    Merge rule-based and ML results into one final verdict per api_key.

    Args:
        risk_results: Output of risk_engine.calculate_risk().
        ml_results:   Output of detector.detect_anomalies().

    Returns:
        List of dicts (api_key, risk_score, anomaly_score, final_label),
        sorted HIGH → MEDIUM → LOW, then by risk_score descending.
    """
    if not risk_results:
        return []

    ml_index = {row["api_key"]: row for row in ml_results}
    label_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    decisions = []
    for row in risk_results:
        key    = row["api_key"]
        ml_row = ml_index.get(key, {})
        decisions.append({
            "api_key":       key,
            "risk_score":    row["risk_score"],
            "anomaly_score": ml_row.get("anomaly_score", 0.0),
            "final_label":   _decide(row["risk_score"], ml_row.get("prediction", "normal")),
        })

    decisions.sort(key=lambda x: (label_order[x["final_label"]], -x["risk_score"]))
    return decisions
