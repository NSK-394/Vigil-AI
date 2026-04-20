"""
agents/detection_agent.py — Reason phase of the agent loop.

Runs the rule engine and ML anomaly detector over the enriched feature set,
merging their outputs into one detection record per API key with confidence scores.
"""

from __future__ import annotations
from risk_engine     import calculate_risk
from detector        import detect_anomalies
from core.confidence import compute_confidence


class DetectionAgent:
    """Reason: rule engine + ML detector → per-key detection dicts with confidence."""

    def analyze(self, enriched_features: list[dict]) -> list[dict]:
        """
        Analyze enriched feature rows and return detection dicts sorted by risk_score desc.

        Each dict contains: api_key, risk_score, anomaly_score, rule_label,
        ml_prediction, rule_confidence, ml_confidence, and all memory-enriched
        pass-through fields.
        """
        if not enriched_features:
            return []

        rule_results = calculate_risk(enriched_features)
        ml_results   = self._run_ml_engine(enriched_features)
        ml_map       = {r["api_key"]: r for r in ml_results}

        detections = []
        for rule in rule_results:
            key  = rule["api_key"]
            ml   = ml_map.get(key, {"anomaly_score": 50.0, "prediction": "normal"})
            feat = next(f for f in enriched_features if f["api_key"] == key)

            detections.append({
                "api_key":            key,
                "risk_score":         rule["risk_score"],
                "anomaly_score":      ml["anomaly_score"],
                "rule_label":         rule["label"],
                "ml_prediction":      ml["prediction"],
                "rule_confidence":    compute_confidence(rule["risk_score"],  engine="rule"),
                "ml_confidence":      compute_confidence(ml["anomaly_score"], engine="ml"),
                "request_velocity":   feat.get("request_velocity", 0.0),
                "historical_avg":     feat.get("historical_avg", 0.0),
                "baseline_deviation": feat.get("baseline_deviation", 0.0),
                "repeat_offender":    feat.get("repeat_offender", False),
                "prior_observations": feat.get("prior_observations", 0),
                "total_requests":     feat.get("total_requests", 0),
                "average_requests":   feat.get("average_requests", 0.0),
                "unique_endpoints":   feat.get("unique_endpoints", 0),
            })

        detections.sort(key=lambda d: d["risk_score"], reverse=True)
        return detections

    def _run_ml_engine(self, features: list[dict]) -> list[dict]:
        """IsolationForest requires >=2 samples; return neutral scores when below threshold."""
        if len(features) < 2:
            return [{"api_key": f["api_key"], "anomaly_score": 50.0, "prediction": "normal"}
                    for f in features]
        try:
            return detect_anomalies(features)
        except Exception:
            return [{"api_key": f["api_key"], "anomaly_score": 50.0, "prediction": "normal"}
                    for f in features]
