"""
final_decision.py
-----------------
The "verdict layer" of the API abuse detection pipeline.

Combines two independent signals into one final judgement per api_key:
  1. Rule-based risk score  (from risk_engine.py)   → human logic
  2. ML anomaly score       (from detector.py)       → machine learning

Why combine both?
  - Rules alone can miss novel attack patterns.
  - ML alone can flag legitimate power users as anomalies.
  - Together they cross-check each other → fewer false positives.

Input  : risk_results   – list of dicts  (api_key, risk_score, label)
         ml_results     – list of dicts  (api_key, anomaly_score, prediction)
Output : list of dicts  (api_key, risk_score, anomaly_score, final_label)
"""


# ──────────────────────────────────────────────
#  THRESHOLDS  –  must match risk_engine.py
# ──────────────────────────────────────────────

RISK_HIGH_THRESHOLD   = 70   # risk_score above this  → HIGH
RISK_MEDIUM_THRESHOLD = 30   # risk_score above this  → at least MEDIUM


# ──────────────────────────────────────────────
#  HELPER FUNCTIONS
# ──────────────────────────────────────────────

def _index_by_key(results: list[dict], key_field: str) -> dict:
    """
    Turn a list of dicts into a lookup dict keyed by api_key.

    Example
    -------
    Input:
      [{"api_key": "k1", "risk_score": 80}, {"api_key": "k2", "risk_score": 20}]
    Output:
      {"k1": {"api_key": "k1", "risk_score": 80}, "k2": ...}

    This lets us do  O(1)  lookups instead of scanning the whole list
    every time we need to match two records.
    """
    return {row[key_field]: row for row in results}


def _decide(risk_score: float, prediction: str) -> str:
    """
    Core decision logic — called once per api_key.

    Priority order (most dangerous condition checked first):
      1. High rule-based risk score  →  HIGH
      2. ML flagged it as anomaly    →  HIGH   (catches what rules miss)
      3. Medium rule-based risk      →  MEDIUM
      4. Everything else             →  LOW

    Parameters
    ----------
    risk_score : float   numeric score from risk_engine (0–100)
    prediction : str     "anomaly" or "normal" from detector

    Returns
    -------
    str  –  "HIGH" | "MEDIUM" | "LOW"
    """

    # Condition 1 & 2 are OR-ed: either one alone is enough for HIGH
    if risk_score > RISK_HIGH_THRESHOLD or prediction == "anomaly":
        return "HIGH"

    # Condition 3: medium risk band (31–70) with no ML flag
    if risk_score > RISK_MEDIUM_THRESHOLD:
        return "MEDIUM"

    # Default: both systems agree this key looks normal
    return "LOW"


# ──────────────────────────────────────────────
#  MAIN FUNCTION
# ──────────────────────────────────────────────

def combine_results(
    risk_results: list[dict],
    ml_results:   list[dict],
) -> list[dict]:
    """
    Merge rule-based and ML results into one final verdict per api_key.

    Parameters
    ----------
    risk_results : list[dict]
        Output of risk_engine.calculate_risk().
        Required keys: api_key, risk_score, label

    ml_results : list[dict]
        Output of detector.detect_anomalies().
        Required keys: api_key, anomaly_score, prediction

    Returns
    -------
    list[dict]
        One dict per api_key found in risk_results, sorted HIGH → LOW:
            api_key        – the API key string
            risk_score     – rule-based score  (0–100)
            anomaly_score  – ML score          (0–100)
            final_label    – "HIGH" | "MEDIUM" | "LOW"

    Notes
    -----
    - api_keys that appear only in ml_results are silently ignored.
    - api_keys with no ML match get anomaly_score = 0 and
      prediction = "normal" as safe defaults.

    Example
    -------
    >>> decisions = combine_results(risk_results, ml_results)
    >>> print(decisions[0])
    {'api_key': 'bot_key_001', 'risk_score': 95, 'anomaly_score': 98.4, 'final_label': 'HIGH'}
    """

    # ── Step 1: Validate ─────────────────────────────────────────────────
    if not risk_results:
        return []

    # ── Step 2: Index ML results by api_key for fast lookup ──────────────
    # Without this we'd need a nested loop  O(n²).
    # With this, each lookup is O(1).
    ml_index = _index_by_key(ml_results, "api_key")

    # ── Step 3: Merge and decide ──────────────────────────────────────────
    decisions = []

    for risk_row in risk_results:
        api_key    = risk_row["api_key"]
        risk_score = risk_row["risk_score"]

        # --- 3a. Find the matching ML row (if it exists) ---
        ml_row = ml_index.get(api_key)   # returns None if key not found

        if ml_row:
            anomaly_score = ml_row["anomaly_score"]
            prediction    = ml_row["prediction"]
        else:
            # No ML result for this key → default to "safe" values
            # so the rule-based score still drives the decision
            anomaly_score = 0.0
            prediction    = "normal"

        # --- 3b. Run the fusion logic ---
        final_label = _decide(risk_score, prediction)

        # --- 3c. Build the merged result row ---
        decisions.append({
            "api_key":       api_key,
            "risk_score":    risk_score,
            "anomaly_score": anomaly_score,
            "final_label":   final_label,
        })

    # ── Step 4: Sort — most dangerous keys bubble to the top ─────────────
    # Primary sort   : final_label  (HIGH > MEDIUM > LOW)
    # Secondary sort : risk_score   (higher score = higher priority)
    label_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}

    decisions.sort(
        key=lambda x: (label_order[x["final_label"]], -x["risk_score"])
    )

    return decisions


# ──────────────────────────────────────────────
#  QUICK DEMO  –  runs only when executed directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from simulator         import generate_logs
        from feature_extractor import extract_features
        from risk_engine       import calculate_risk
        from detector          import detect_anomalies

        logs         = generate_logs(500)
        features     = extract_features(logs)
        risk_results = calculate_risk(features)
        ml_results   = detect_anomalies(features)

    except ImportError:
        # Fallback: hand-crafted data so the file runs standalone
        risk_results = [
            {"api_key": "bot_key_001",  "risk_score": 95, "label": "HIGH"},
            {"api_key": "bot_key_002",  "risk_score": 75, "label": "HIGH"},
            {"api_key": "user_key_010", "risk_score": 45, "label": "MEDIUM"},
            {"api_key": "user_key_022", "risk_score": 10, "label": "LOW"},
            {"api_key": "user_key_033", "risk_score": 5,  "label": "LOW"},
        ]
        ml_results = [
            {"api_key": "bot_key_001",  "anomaly_score": 97.4, "prediction": "anomaly"},
            {"api_key": "bot_key_002",  "anomaly_score": 88.1, "prediction": "anomaly"},
            {"api_key": "user_key_010", "anomaly_score": 42.0, "prediction": "normal"},
            {"api_key": "user_key_022", "anomaly_score": 12.3, "prediction": "normal"},
            {"api_key": "user_key_033", "anomaly_score": 8.5,  "prediction": "normal"},
        ]

    decisions = combine_results(risk_results, ml_results)

    # ── Summary counts ────────────────────────────────────────────────────
    high_list   = [d for d in decisions if d["final_label"] == "HIGH"]
    medium_list = [d for d in decisions if d["final_label"] == "MEDIUM"]
    low_list    = [d for d in decisions if d["final_label"] == "LOW"]

    # ── Pretty-print table ────────────────────────────────────────────────
    print(f"\n{'API KEY':<18}  {'RISK':>6}  {'ANOMALY':>8}  {'FINAL LABEL':<12}")
    print("─" * 52)

    for d in decisions[:20]:
        if d["final_label"] == "HIGH":
            icon = "🔴"
        elif d["final_label"] == "MEDIUM":
            icon = "🟡"
        else:
            icon = "🟢"

        print(
            f"{d['api_key']:<18}  "
            f"{d['risk_score']:>6}  "
            f"{d['anomaly_score']:>8}  "
            f"{icon} {d['final_label']}"
        )

    print(f"\nFinal Summary →  🔴 HIGH: {len(high_list)}   🟡 MEDIUM: {len(medium_list)}   🟢 LOW: {len(low_list)}")