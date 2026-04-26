"""
storage.py — CSV persistence layer.

Appends pipeline output to CSV files, creating them with headers on
first write. All three public functions follow the same pattern.
"""

import os
import pandas as pd


def _save(data: list[dict], filepath: str, label: str) -> None:
    if not data:
        return
    df         = pd.DataFrame(data)
    file_exists = os.path.isfile(filepath)
    df.to_csv(filepath, mode="a" if file_exists else "w",
              index=False, header=not file_exists, encoding="utf-8")
    action = "Appended" if file_exists else "Created"
    print(f"[storage] {action} '{filepath}' — {len(df)} {label} row(s).")


def save_logs(logs: list[dict], filename: str = "logs.csv") -> None:
    """Persist raw log entries to CSV."""
    _save(logs, filename, "log")


def save_features(features: list[dict], filename: str = "features.csv") -> None:
    """Persist per-key feature rows to CSV."""
    _save(features, filename, "feature")


def save_results(results: list[dict], filename: str = "results.csv") -> None:
    """Persist final decision rows to CSV."""
    _save(results, filename, "result")
