"""
feature_extractor.py — Per-key behavioral feature engineering.

Groups raw API logs by api_key and computes four aggregate features
that capture bot-like vs human-like traffic patterns.
"""

import statistics
from collections import defaultdict


def extract_features(logs: list[dict]) -> list[dict]:
    """
    Aggregate raw log entries into one feature vector per api_key.

    Args:
        logs: Raw log dicts from simulator.generate_logs().
              Required keys: api_key, endpoint, request_count.

    Returns:
        One dict per unique api_key with keys:
            api_key, total_requests, average_requests,
            unique_endpoints, request_variance
    """
    if not logs:
        return []

    grouped: dict[str, list] = defaultdict(list)
    for log in logs:
        grouped[log["api_key"]].append(log)

    features = []
    for api_key, key_logs in grouped.items():
        counts = [log["request_count"] for log in key_logs]
        features.append({
            "api_key":          api_key,
            "total_requests":   sum(counts),
            "average_requests": round(sum(counts) / len(counts), 2),
            "unique_endpoints": len({log["endpoint"] for log in key_logs}),
            "request_variance": round(statistics.variance(counts), 2) if len(counts) > 1 else 0.0,
        })

    return features
