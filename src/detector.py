"""
detector.py — IsolationForest anomaly detection.

Trains an unsupervised model on the current cycle's feature set and
scores each api_key for statistical outlier-ness. No labels required.
"""

import numpy as np
from sklearn.ensemble      import IsolationForest
from sklearn.preprocessing import StandardScaler

FEATURE_COLUMNS = [
    "total_requests",
    "average_requests",
    "unique_endpoints",
    "request_variance",
]
CONTAMINATION = 0.2
RANDOM_STATE  = 42


def _build_matrix(features: list[dict]) -> tuple[list[str], np.ndarray]:
    """Extract api_keys and numeric feature matrix from feature dicts."""
    api_keys = [row["api_key"] for row in features]
    X = np.array([[row[col] for col in FEATURE_COLUMNS] for row in features], dtype=float)
    return api_keys, X


def _normalize_scores(raw_scores: np.ndarray) -> np.ndarray:
    """Convert IsolationForest negative scores to a 0–100 anomaly scale."""
    flipped = -raw_scores
    min_val, max_val = flipped.min(), flipped.max()
    if max_val == min_val:
        return np.full_like(flipped, 50.0)
    return np.round((flipped - min_val) / (max_val - min_val) * 100, 2)


def detect_anomalies(features: list[dict]) -> list[dict]:
    """
    Run IsolationForest on the feature set and score each api_key.

    Args:
        features: Output of feature_extractor.extract_features().
                  Requires at least 2 rows.

    Returns:
        List of dicts sorted by anomaly_score descending:
            api_key, anomaly_score (0-100), prediction ("anomaly"|"normal")

    Raises:
        ValueError: If fewer than 2 feature rows are provided.
    """
    if not features:
        return []
    if len(features) < 2:
        raise ValueError("IsolationForest requires at least 2 feature rows.")

    api_keys, X = _build_matrix(features)
    X_scaled = StandardScaler().fit_transform(X)

    model = IsolationForest(
        n_estimators=100,
        contamination=CONTAMINATION,
        random_state=RANDOM_STATE,
    )
    raw_predictions = model.fit_predict(X_scaled)
    anomaly_scores  = _normalize_scores(model.score_samples(X_scaled))

    results = [
        {
            "api_key":       api_keys[i],
            "anomaly_score": float(anomaly_scores[i]),
            "prediction":    "normal" if raw_predictions[i] == 1 else "anomaly",
        }
        for i in range(len(api_keys))
    ]
    results.sort(key=lambda x: x["anomaly_score"], reverse=True)
    return results
