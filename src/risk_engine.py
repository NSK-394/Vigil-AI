"""
risk_engine.py — Rule-based risk scoring engine.

Scores each api_key 0–100 based on heuristic rules that mirror
how a SOC analyst would flag suspicious behavior manually.
"""

# ── Thresholds ─────────────────────────────────────────────────────────────
AVG_REQ_LOW_THRESHOLD   = 50
AVG_REQ_HIGH_THRESHOLD  = 200
ENDPOINT_LOW_THRESHOLD  = 2
ENDPOINT_MED_THRESHOLD  = 4
VARIANCE_LOW_THRESHOLD  = 10
VARIANCE_HIGH_THRESHOLD = 100

LABEL_LOW_MAX    = 30
LABEL_MEDIUM_MAX = 70


# ── Partial scorers ────────────────────────────────────────────────────────

def _score_average_requests(avg: float) -> int:
    if avg > 40:
        return 40
    if avg > 20:
        return 20
    return 0


def _score_unique_endpoints(unique: int) -> int:
    if unique == 1:
        return 30
    if unique <= 2:
        return 15
    return 0


def _score_request_variance(variance: float) -> int:
    if variance > 10:
        return 20
    if variance > 5:
        return 10
    return 0


def _label(score: int) -> str:
    if score <= LABEL_LOW_MAX:
        return "LOW"
    if score <= LABEL_MEDIUM_MAX:
        return "MEDIUM"
    return "HIGH"


# ── Public API ─────────────────────────────────────────────────────────────

def calculate_risk(features: list[dict]) -> list[dict]:
    """
    Apply heuristic rules to each feature row and return a risk assessment.

    Args:
        features: Output of feature_extractor.extract_features().

    Returns:
        List of dicts with keys: api_key, risk_score (0-100), label.
    """
    results = []
    for f in features:
        score = (
            _score_average_requests(f["average_requests"])
            + _score_unique_endpoints(f["unique_endpoints"])
            + _score_request_variance(f["request_variance"])
        )
        # Extreme-volume bonus
        if f["average_requests"] > 80:
            score += 20

        score = min(score, 100)
        results.append({
            "api_key":    f["api_key"],
            "risk_score": score,
            "label":      _label(score),
        })

    return results
