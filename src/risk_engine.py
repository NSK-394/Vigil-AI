"""
risk_engine.py
--------------
Rule-based risk scoring engine for API abuse detection.

Takes per-api_key feature rows (from feature_extractor.py) and assigns:
  - A numeric risk_score  (0 – 100)
  - A human-readable label  LOW / MEDIUM / HIGH

No ML yet — pure logic rules that mirror how a real SOC analyst thinks:
  "This key made 800 requests per entry and only hit /login … that's sketchy."
"""


# ──────────────────────────────────────────────
#  THRESHOLDS  –  tweak these to tune sensitivity
# ──────────────────────────────────────────────

# average_requests: anything above this is suspicious
AVG_REQ_LOW_THRESHOLD    = 50    # mild suspicion starts here
AVG_REQ_HIGH_THRESHOLD   = 200   # strong suspicion above this

# unique_endpoints: few endpoints = focused / automated behaviour
ENDPOINT_LOW_THRESHOLD   = 2     # hitting only 1–2 endpoints is a red flag
ENDPOINT_MED_THRESHOLD   = 4     # 3–4 endpoints is mildly suspicious

# request_variance: near-zero = robotic (bots are perfectly consistent)
VARIANCE_LOW_THRESHOLD   = 10    # very low variance → automated
VARIANCE_HIGH_THRESHOLD  = 100   # high variance → human-like randomness

# Label bands
LABEL_LOW_MAX    = 30
LABEL_MEDIUM_MAX = 70
# anything above 70 → HIGH


# ──────────────────────────────────────────────
#  HELPER : single-feature scorers
# ──────────────────────────────────────────────

def _score_average_requests(avg: float) -> int:
    """
    High average requests per log entry → more risk.

    Returns a partial score out of 40 points.
    (We weight this highest because it's the strongest bot signal.)
    """
    if avg > AVG_REQ_HIGH_THRESHOLD:
        return 40       # very high average → maximum points
    elif avg > AVG_REQ_LOW_THRESHOLD:
        return 20       # moderate average → half points
    else:
        return 0        # normal range → no points added


def _score_unique_endpoints(unique: int) -> int:
    """
    Few unique endpoints → more risk.
    Bots typically hammer 1–2 endpoints (login, search).

    Returns a partial score out of 35 points.
    """
    if unique <= ENDPOINT_LOW_THRESHOLD:
        return 35       # very focused → high risk contribution
    elif unique <= ENDPOINT_MED_THRESHOLD:
        return 15       # somewhat focused → moderate contribution
    else:
        return 0        # diverse browsing → normal behaviour


def _score_request_variance(variance: float) -> int:
    """
    Near-zero variance → robotic → more risk.
    High variance → unpredictable → human-like → less risk.

    Returns a partial score out of 25 points.
    """
    if variance < VARIANCE_LOW_THRESHOLD:
        return 25       # near-zero variance → looks automated
    elif variance < VARIANCE_HIGH_THRESHOLD:
        return 10       # some variance but still a bit flat
    else:
        return 0        # lots of variance → natural human behaviour


def _get_label(score: int) -> str:
    """Convert a numeric score to a human-readable risk label."""
    if score <= LABEL_LOW_MAX:
        return "LOW"
    elif score <= LABEL_MEDIUM_MAX:
        return "MEDIUM"
    else:
        return "HIGH"


# ──────────────────────────────────────────────
#  MAIN FUNCTION
# ──────────────────────────────────────────────

def calculate_risk(features):
    results = []

    for f in features:
        risk_score = 0

        avg = f["average_requests"]
        unique = f["unique_endpoints"]
        var = f["request_variance"]

        # Rule 1: High request frequency
        if avg > 40:
            risk_score += 40
        elif avg > 20:
            risk_score += 20

        # Rule 2: Low endpoint diversity (bot behavior)
        if unique == 1:
            risk_score += 30
        elif unique <= 2:
            risk_score += 15

        # Rule 3: High variance (irregular activity)
        if var > 10:
            risk_score += 20
        elif var > 5:
            risk_score += 10

        # Bonus: extreme behavior
        if avg > 80:
            risk_score += 20

        # Cap risk score at 100
        risk_score = min(risk_score, 100)

        # Labeling
        if risk_score <= 30:
            label = "LOW"
        elif risk_score <= 70:
            label = "MEDIUM"
        else:
            label = "HIGH"

        results.append({
            "api_key": f["api_key"],
            "risk_score": risk_score,
            "label": label
        })

    return results


# ──────────────────────────────────────────────
#  QUICK DEMO  –  runs only when executed directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from simulator        import generate_logs
        from feature_extractor import extract_features

        logs     = generate_logs(500)
        features = extract_features(logs)

    except ImportError:
        # Fallback: hand-crafted feature rows to test standalone
        features = [
            {"api_key": "bot_key_001",  "total_requests": 4500, "average_requests": 750.0, "unique_endpoints": 1, "request_variance": 3.2},
            {"api_key": "bot_key_002",  "total_requests": 2100, "average_requests": 420.0, "unique_endpoints": 2, "request_variance": 8.5},
            {"api_key": "user_key_010", "total_requests": 45,   "average_requests": 9.0,   "unique_endpoints": 5, "request_variance": 210.4},
            {"api_key": "user_key_022", "total_requests": 90,   "average_requests": 18.0,  "unique_endpoints": 3, "request_variance": 55.0},
        ]

    results = calculate_risk(features)

    # ── Pretty-print the output table ────────────────────────────────────
    HIGH   = [r for r in results if r["label"] == "HIGH"]
    MEDIUM = [r for r in results if r["label"] == "MEDIUM"]
    LOW    = [r for r in results if r["label"] == "LOW"]

    print(f"\n{'API KEY':<18}  {'RISK SCORE':>10}  {'LABEL':<8}")
    print("─" * 42)

    for r in results[:20]:                     # show top 20
        # Add a visual indicator per label
        icon = "🔴" if r["label"] == "HIGH" else "🟡" if r["label"] == "MEDIUM" else "🟢"
        print(f"{r['api_key']:<18}  {r['risk_score']:>10}  {icon} {r['label']}")

    print(f"\nSummary →  🔴 HIGH: {len(HIGH)}   🟡 MEDIUM: {len(MEDIUM)}   🟢 LOW: {len(LOW)}")