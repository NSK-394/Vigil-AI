"""
feature_extractor.py
--------------------
Takes raw API logs and turns them into per-api_key feature rows.
These features are what the anomaly detection model actually learns from.

Input  : list of log dicts  (from simulator.py → generate_logs)
Output : list of feature dicts, one row per unique api_key
"""

import statistics


# ──────────────────────────────────────────────
#  MAIN FUNCTION
# ──────────────────────────────────────────────

def extract_features(logs: list[dict]) -> list[dict]:
    """
    Group logs by api_key and compute behavioural features for each key.

    Parameters
    ----------
    logs : list[dict]
        Raw log entries. Each dict must have at least:
            api_key, endpoint, request_count, timestamp, ip_address

    Returns
    -------
    list[dict]
        One dict per unique api_key with the keys:
            api_key, total_requests, average_requests,
            unique_endpoints, request_variance

    Example
    -------
    >>> from simulator import generate_logs
    >>> logs = generate_logs(200)
    >>> features = extract_features(logs)
    >>> print(features[0])
    {'api_key': 'user_key_007', 'total_requests': 42, ...}
    """

    # ── Step 1: Validate input ───────────────────────────────────────────
    if not logs:
        return []   # nothing to process → return empty list

    # ── Step 2: Group logs by api_key ────────────────────────────────────
    # We build a dict where each key is an api_key and the value is
    # a list of ALL log entries that belong to that api_key.
    #
    #   grouped = {
    #       "user_key_001": [ {log1}, {log2}, ... ],
    #       "bot_key_003":  [ {log5}, {log6}, ... ],
    #       ...
    #   }

    grouped = {}

    for log in logs:
        key = log["api_key"]

        if key not in grouped:
            grouped[key] = []       # first time we see this api_key → create bucket

        grouped[key].append(log)    # add this log to the right bucket

    # ── Step 3: Calculate features for each api_key ──────────────────────
    features = []

    for api_key, key_logs in grouped.items():

        # --- 3a. Collect all request_count values for this key ---
        # e.g.  [3, 7, 2, 5]  for a normal user
        #       [450, 800, 600]  for a bot
        counts = [log["request_count"] for log in key_logs]

        # --- 3b. total_requests ---
        # Sum of every request this key made across all log entries.
        # Bots will have a very high total.
        total_requests = sum(counts)

        # --- 3c. average_requests ---
        # Mean requests per log entry.
        # Bots average hundreds per entry; normal users average < 15.
        average_requests = round(total_requests / len(counts), 2)

        # --- 3d. unique_endpoints ---
        # How many different API endpoints this key touched.
        # Normal users browse around; bots hammer 1–2 endpoints.
        unique_endpoints = len(set(log["endpoint"] for log in key_logs))

        # --- 3e. request_variance ---
        # How much the request counts fluctuate across entries.
        # A variance of 0 means every entry had the exact same count
        # → a strong bot signal (perfectly automated behaviour).
        # statistics.variance needs at least 2 data points.
        if len(counts) > 1:
            request_variance = round(statistics.variance(counts), 2)
        else:
            request_variance = 0.0  # only one log entry → can't compute variance

        # --- 3f. Pack everything into a feature row ---
        feature_row = {
            "api_key":          api_key,
            "total_requests":   total_requests,
            "average_requests": average_requests,
            "unique_endpoints": unique_endpoints,
            "request_variance": request_variance,
        }

        features.append(feature_row)

    # ── Step 4: Return the full feature list ─────────────────────────────
    return features


# ──────────────────────────────────────────────
#  QUICK DEMO  –  runs only when executed directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    # Import the simulator we built earlier to get sample logs
    try:
        from simulator import generate_logs
        logs = generate_logs(300)
    except ImportError:
        # Fallback: tiny hand-crafted sample so the file runs standalone
        logs = [
            {"api_key": "user_key_001", "endpoint": "/api/login",    "request_count": 3,  "timestamp": "2024-01-01 10:00:00", "ip_address": "192.168.1.1"},
            {"api_key": "user_key_001", "endpoint": "/api/products",  "request_count": 7,  "timestamp": "2024-01-01 10:05:00", "ip_address": "192.168.1.1"},
            {"api_key": "bot_key_001",  "endpoint": "/api/login",     "request_count": 500,"timestamp": "2024-01-01 10:00:01", "ip_address": "45.33.10.5"},
            {"api_key": "bot_key_001",  "endpoint": "/api/login",     "request_count": 480,"timestamp": "2024-01-01 10:00:03", "ip_address": "45.33.10.5"},
        ]

    features = extract_features(logs)

    # Print a nicely formatted table
    print(f"\n{'API KEY':<18}  {'TOTAL REQ':>9}  {'AVG REQ':>8}  {'UNIQ EP':>7}  {'VARIANCE':>10}")
    print("─" * 65)

    # Sort by total_requests descending so bots float to the top
    for row in sorted(features, key=lambda x: x["total_requests"], reverse=True)[:15]:
        print(
            f"{row['api_key']:<18}  "
            f"{row['total_requests']:>9}  "
            f"{row['average_requests']:>8}  "
            f"{row['unique_endpoints']:>7}  "
            f"{row['request_variance']:>10}"
        )

    print(f"\nTotal unique api_keys processed: {len(features)}")