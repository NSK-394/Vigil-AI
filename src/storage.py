"""
storage.py
----------
Handles saving pipeline data to CSV files.

Three save functions — one per data type:
  save_logs()      → raw API log entries       (from simulator.py)
  save_features()  → per-key feature rows      (from feature_extractor.py)
  save_results()   → final verdict rows        (from final_decision.py)

Behaviour:
  - File does NOT exist → create it with headers.
  - File DOES exist     → append rows, no duplicate header written.

All functions follow the exact same pattern so the code stays predictable.
"""

import os
import pandas as pd


# ──────────────────────────────────────────────
#  HELPER FUNCTION  (shared logic lives here)
# ──────────────────────────────────────────────

def _save_to_csv(data: list[dict], filename: str, label: str) -> None:
    """
    Core save routine used by all three public functions.

    Parameters
    ----------
    data     : list of dicts to persist
    filename : path to the target CSV file  (e.g. "logs.csv")
    label    : human-readable name used only in print messages

    Steps
    -----
    1. Validate the input list isn't empty.
    2. Convert to a pandas DataFrame.
    3. Check if the file already exists.
       - Yes → append WITHOUT writing the header again.
       - No  → write fresh file WITH the header.
    4. Print a confirmation message.
    """

    # ── Step 1: Guard against empty input ────────────────────────────────
    if not data:
        print(f"[storage] ⚠️  No {label} to save — list is empty.")
        return

    # ── Step 2: Convert list of dicts → DataFrame ────────────────────────
    # pandas figures out the column names from the dict keys automatically.
    df = pd.DataFrame(data)

    # ── Step 3: Decide whether to create or append ───────────────────────
    file_exists = os.path.isfile(filename)

    if file_exists:
        # Append mode — 'a' adds rows below existing content.
        # header=False prevents writing column names a second time.
        df.to_csv(filename, mode="a", index=False, header=False)
        action = "Appended"
    else:
        # Write mode — 'w' creates a brand-new file.
        # header=True writes column names on the first line.
        df.to_csv(filename, mode="w", index=False, header=True)
        action = "Created"

    # ── Step 4: Confirm to the caller ────────────────────────────────────
    print(f"[storage] ✅ {action} '{filename}'  →  {len(df)} {label} row(s) saved.")


# ──────────────────────────────────────────────
#  PUBLIC FUNCTIONS
# ──────────────────────────────────────────────

def save_logs(logs: list[dict], filename: str = "logs.csv") -> None:
    """
    Save raw API log entries to a CSV file.

    Expected columns (from simulator.py → generate_logs):
        api_key, endpoint, request_count, timestamp, ip_address, label

    Parameters
    ----------
    logs     : list of log dicts
    filename : output CSV path  (default: "logs.csv")

    Example
    -------
    >>> from simulator import generate_logs
    >>> logs = generate_logs(500)
    >>> save_logs(logs, "data/logs.csv")
    [storage] ✅ Created 'data/logs.csv'  →  500 logs row(s) saved.
    """
    _save_to_csv(logs, filename, label="logs")


def save_features(features: list[dict], filename: str = "features.csv") -> None:
    """
    Save per-api_key feature rows to a CSV file.

    Expected columns (from feature_extractor.py → extract_features):
        api_key, total_requests, average_requests,
        unique_endpoints, request_variance

    Parameters
    ----------
    features : list of feature dicts
    filename : output CSV path  (default: "features.csv")

    Example
    -------
    >>> from feature_extractor import extract_features
    >>> features = extract_features(logs)
    >>> save_features(features, "data/features.csv")
    [storage] ✅ Created 'data/features.csv'  →  60 features row(s) saved.
    """
    _save_to_csv(features, filename, label="features")


def save_results(results: list[dict], filename: str = "results.csv") -> None:
    """
    Save final decision rows to a CSV file.

    Expected columns (from final_decision.py → combine_results):
        api_key, risk_score, anomaly_score, final_label

    Also works with intermediate outputs:
        - risk_engine    → api_key, risk_score, label
        - detector       → api_key, anomaly_score, prediction

    Parameters
    ----------
    results  : list of result dicts
    filename : output CSV path  (default: "results.csv")

    Example
    -------
    >>> from final_decision import combine_results
    >>> decisions = combine_results(risk_results, ml_results)
    >>> save_results(decisions, "data/results.csv")
    [storage] ✅ Created 'data/results.csv'  →  60 results row(s) saved.
    """
    _save_to_csv(results, filename, label="results")


# ──────────────────────────────────────────────
#  QUICK DEMO  –  runs only when executed directly
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import os
    import sys
    if sys.stdout.encoding.lower() != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')

    try:
        from simulator         import generate_logs
        from feature_extractor import extract_features
        from risk_engine       import calculate_risk
        from detector          import detect_anomalies
        from final_decision    import combine_results

        # ── Run the full pipeline ─────────────────────────────────────────
        print("\n[demo] Running full pipeline …\n")

        logs      = generate_logs(300)
        features  = extract_features(logs)
        risk      = calculate_risk(features)
        ml        = detect_anomalies(features)
        decisions = combine_results(risk, ml)

    except ImportError:
        # Fallback: tiny hand-crafted data
        print("\n[demo] Pipeline modules not found — using sample data.\n")

        logs = [
            {"api_key": "user_key_001", "endpoint": "/api/login",    "request_count": 5,   "timestamp": "2024-01-01 10:00:00", "ip_address": "192.168.1.1", "label": "normal"},
            {"api_key": "bot_key_001",  "endpoint": "/api/login",    "request_count": 700, "timestamp": "2024-01-01 10:00:02", "ip_address": "45.33.10.5",  "label": "bot"},
        ]
        features = [
            {"api_key": "user_key_001", "total_requests": 5,   "average_requests": 5.0,   "unique_endpoints": 3, "request_variance": 0.0},
            {"api_key": "bot_key_001",  "total_requests": 700, "average_requests": 700.0, "unique_endpoints": 1, "request_variance": 0.0},
        ]
        decisions = [
            {"api_key": "bot_key_001",  "risk_score": 95, "anomaly_score": 97.4, "final_label": "HIGH"},
            {"api_key": "user_key_001", "risk_score": 5,  "anomaly_score": 8.1,  "final_label": "LOW"},
        ]

    # ── Make output folder ────────────────────────────────────────────────
    os.makedirs("data", exist_ok=True)

    # ── Save all three data types ─────────────────────────────────────────
    print("── Saving data ──────────────────────────────────")
    save_logs(logs,           "data/logs.csv")
    save_features(features,   "data/features.csv")
    save_results(decisions,   "data/results.csv")

    # ── Demo: calling again appends rows ──────────────────────────────────
    print("\n── Appending same data again (testing append mode) ──")
    save_logs(logs,           "data/logs.csv")
    save_features(features,   "data/features.csv")
    save_results(decisions,   "data/results.csv")

    # ── Verify: read back and show row counts ─────────────────────────────
    print("\n── Verification (row counts after append) ───────────")
    for path in ["data/logs.csv", "data/features.csv", "data/results.csv"]:
        df = pd.read_csv(path)
        print(f"  {path:<28}  →  {len(df)} rows,  {list(df.columns)}")