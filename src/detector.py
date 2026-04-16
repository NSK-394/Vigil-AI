"""
detector.py
-----------
Machine-learning layer of the API abuse detection pipeline.

Uses scikit-learn's Isolation Forest — an unsupervised algorithm that
detects outliers WITHOUT needing labelled training data.

How Isolation Forest works (plain English):
  - It builds many random decision trees.
  - Normal points are "hard to isolate" → need many splits to separate.
  - Anomalies are "easy to isolate"    → need very few splits to separate.
  - The fewer splits needed, the more anomalous the point.

Input  : list of feature dicts  (from feature_extractor.py)
Output : list of result dicts   (api_key, anomaly_score, prediction)
"""

import numpy as np
from sklearn.ensemble         import IsolationForest
from sklearn.preprocessing    import StandardScaler


# ──────────────────────────────────────────────
#  CONFIG
# ──────────────────────────────────────────────

# The four numerical columns the model will train on.
# Order matters — keep it consistent everywhere.
FEATURE_COLUMNS = [
    "total_requests",
    "average_requests",
    "unique_endpoints",
    "request_variance",
]

# contamination = the fraction of the dataset we expect to be anomalies.
# 0.2 means "I expect roughly 20% of keys to be bots / abusers."
# Tune this based on your real traffic split.
CONTAMINATION = 0.2

# Random seed for reproducibility (same seed → same results every run)
RANDOM_STATE = 42


# ──────────────────────────────────────────────
#  HELPER FUNCTIONS
# ──────────────────────────────────────────────

def _build_matrix(features: list[dict]) -> tuple[list[str], np.ndarray]:
    """
    Convert a list of feature dicts into:
      - api_keys : list of api_key strings  (to re-attach later)
      - X        : 2-D numpy array of shape (n_keys, 4)

    Example
    -------
    Input:
      [{"api_key": "k1", "total_requests": 50, ...}, ...]
    Output:
      ["k1", ...],  array([[50, ...], ...])
    """
    api_keys = []
    rows     = []

    for row in features:
        api_keys.append(row["api_key"])

        # Extract only the numeric columns — in a fixed order
        numeric_row = [row[col] for col in FEATURE_COLUMNS]
        rows.append(numeric_row)

    # Stack into a 2-D numpy array  (required by scikit-learn)
    X = np.array(rows, dtype=float)
    return api_keys, X


def _scale(X: np.ndarray) -> np.ndarray:
    """
    Normalise features so no single column dominates just because its
    numbers are bigger (e.g. total_requests can be 1000s while
    unique_endpoints is 1–10).

    StandardScaler transforms each column to mean=0, std=1.
    """
    scaler = StandardScaler()
    return scaler.fit_transform(X)


def _score_to_probability(raw_scores: np.ndarray) -> np.ndarray:
    """
    Isolation Forest's score_samples() returns negative values.
    More negative  →  more anomalous.

    We convert to a 0–100 scale for readability:
      - 100 = most anomalous
      - 0   = most normal

    Steps:
      1. Flip the sign so higher = more anomalous.
      2. Min-max normalise to [0, 1].
      3. Scale to [0, 100] and round.
    """
    # Step 1: flip  (now higher = worse)
    flipped = -raw_scores

    # Step 2: min-max normalise to [0, 1]
    min_val = flipped.min()
    max_val = flipped.max()

    if max_val == min_val:
        # Edge case: all scores identical → everything gets 50
        normalised = np.full_like(flipped, 0.5)
    else:
        normalised = (flipped - min_val) / (max_val - min_val)

    # Step 3: scale to 0–100
    return np.round(normalised * 100, 2)


# ──────────────────────────────────────────────
#  MAIN FUNCTION
# ──────────────────────────────────────────────

def detect_anomalies(features: list[dict]) -> list[dict]:
    """
    Run Isolation Forest on the feature set and label each api_key.

    Parameters
    ----------
    features : list[dict]
        Output of feature_extractor.extract_features().

    Returns
    -------
    list[dict]
        One dict per api_key, sorted highest anomaly score first:
            api_key        – the API key string
            anomaly_score  – 0 (very normal) → 100 (very anomalous)
            prediction     – "anomaly" | "normal"

    Example
    -------
    >>> results = detect_anomalies(features)
    >>> print(results[0])
    {'api_key': 'bot_key_003', 'anomaly_score': 97.4, 'prediction': 'anomaly'}
    """

    # ── Step 1: Validate ─────────────────────────────────────────────────
    if not features:
        return []

    if len(features) < 2:
        # Isolation Forest needs at least 2 samples to compare against
        raise ValueError("Need at least 2 feature rows to run anomaly detection.")

    # ── Step 2: Build the numeric matrix ─────────────────────────────────
    # Separate api_key strings from the numbers the model needs.
    api_keys, X = _build_matrix(features)

    # ── Step 3: Scale the features ───────────────────────────────────────
    # Puts all columns on the same scale so variance/total_requests
    # don't overpower unique_endpoints (which is much smaller).
    X_scaled = _scale(X)

    # ── Step 4: Train Isolation Forest ───────────────────────────────────
    # n_estimators = number of trees  (more trees = more stable results)
    # contamination = expected fraction of anomalies in the dataset
    model = IsolationForest(
        n_estimators  = 100,
        contamination = CONTAMINATION,
        random_state  = RANDOM_STATE,
    )

    # fit_predict trains the model AND returns predictions in one call:
    #   +1  →  normal
    #   -1  →  anomaly
    raw_predictions = model.fit_predict(X_scaled)

    # ── Step 5: Get raw anomaly scores ───────────────────────────────────
    # score_samples() gives the underlying score for each data point.
    # We convert these to a 0–100 human-readable scale.
    raw_scores     = model.score_samples(X_scaled)
    anomaly_scores = _score_to_probability(raw_scores)

    # ── Step 6: Build result list ─────────────────────────────────────────
    results = []

    for i, api_key in enumerate(api_keys):
        # Convert sklearn's +1/-1 into readable labels
        prediction = "normal" if raw_predictions[i] == 1 else "anomaly"

        results.append({
            "api_key":       api_key,
            "anomaly_score": float(anomaly_scores[i]),
            "prediction":    prediction,
        })

    # ── Step 7: Sort — most suspicious keys first ─────────────────────────
    results.sort(key=lambda x: x["anomaly_score"], reverse=True)

    return results


# ──────────────────────────────────────────────
#  QUICK DEMO  –  runs only when executed directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    try:
        from simulator         import generate_logs
        from feature_extractor import extract_features

        logs     = generate_logs(500)
        features = extract_features(logs)

    except ImportError:
        # Fallback: hand-crafted features so the file runs standalone
        features = [
            {"api_key": "bot_key_001",  "total_requests": 4500, "average_requests": 750.0, "unique_endpoints": 1, "request_variance": 3.0},
            {"api_key": "bot_key_002",  "total_requests": 3200, "average_requests": 533.0, "unique_endpoints": 1, "request_variance": 5.5},
            {"api_key": "user_key_001", "total_requests": 40,   "average_requests": 8.0,   "unique_endpoints": 6, "request_variance": 180.0},
            {"api_key": "user_key_002", "total_requests": 55,   "average_requests": 11.0,  "unique_endpoints": 5, "request_variance": 220.0},
            {"api_key": "user_key_003", "total_requests": 30,   "average_requests": 6.0,   "unique_endpoints": 4, "request_variance": 95.0},
        ]

    results = detect_anomalies(features)

    # ── Pretty-print ──────────────────────────────────────────────────────
    anomalies = [r for r in results if r["prediction"] == "anomaly"]
    normals   = [r for r in results if r["prediction"] == "normal"]

    print(f"\n{'API KEY':<18}  {'ANOMALY SCORE':>13}  {'PREDICTION':<10}")
    print("─" * 48)

    for r in results[:20]:
        icon = "🚨" if r["prediction"] == "anomaly" else "✅"
        print(
            f"{r['api_key']:<18}  "
            f"{r['anomaly_score']:>13}  "
            f"{icon} {r['prediction']}"
        )

    print(f"\nSummary →  🚨 Anomalies: {len(anomalies)}   ✅ Normal: {len(normals)}")