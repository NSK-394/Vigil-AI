"""
DetectionAgent — Reason phase of the agent loop.

Runs the rule engine and ML anomaly detector in parallel over the
enriched feature set. Merges their outputs into a single detection
record per API key that includes confidence scores.

The confidence value tells DecisionAgent how much weight to give each
engine — high confidence means the engine is far from its ambiguous
midpoint (score=50) and its vote should dominate the fusion.
"""

from __future__ import annotations
from risk_engine  import calculate_risk
from detector     import detect_anomalies
from core.confidence import compute_confidence


class DetectionAgent:
    """
    Reason: run rule engine + ML detector → produce per-key detection dicts.
    """

    # ── Public API ─────────────────────────────────────────────────────────

    def analyze(self, enriched_features: list[dict]) -> list[dict]:
        """
        Analyze a list of enriched feature rows.

        Args:
            enriched_features: Output of MonitorAgent.observe() — one dict
                               per api_key, including memory-enriched fields.

        Returns:
            List of detection dicts, one per api_key, sorted by risk_score desc.
            Each dict contains:
                api_key, risk_score, anomaly_score, rule_label,
                ml_prediction, rule_confidence, ml_confidence,
                + all memory-enriched fields passed through.
        """
        if not enriched_features:
            return []

        rule_results = self._run_rule_engine(enriched_features)
        ml_results   = self._run_ml_engine(enriched_features)

        ml_map = {r["api_key"]: r for r in ml_results}

        detections = []
        for rule in rule_results:
            key = rule["api_key"]
            ml  = ml_map.get(key, {"anomaly_score": 50.0, "prediction": "normal"})
            feat = next(f for f in enriched_features if f["api_key"] == key)

            rule_conf = compute_confidence(rule["risk_score"],  engine="rule")
            ml_conf   = compute_confidence(ml["anomaly_score"], engine="ml")

            detections.append({
                # Core scores
                "api_key":        key,
                "risk_score":     rule["risk_score"],
                "anomaly_score":  ml["anomaly_score"],
                "rule_label":     rule["label"],
                "ml_prediction":  ml["prediction"],
                # Confidence signals
                "rule_confidence": rule_conf,
                "ml_confidence":   ml_conf,
                # Memory-enriched fields (pass-through for DecisionAgent)
                "request_velocity":   feat.get("request_velocity", 0.0),
                "historical_avg":     feat.get("historical_avg", 0.0),
                "baseline_deviation": feat.get("baseline_deviation", 0.0),
                "repeat_offender":    feat.get("repeat_offender", False),
                "prior_observations": feat.get("prior_observations", 0),
                # Original feature values (for explainer)
                "total_requests":   feat.get("total_requests", 0),
                "average_requests": feat.get("average_requests", 0.0),
                "unique_endpoints": feat.get("unique_endpoints", 0),
            })

        detections.sort(key=lambda d: d["risk_score"], reverse=True)
        return detections

    # ── Internal helpers ───────────────────────────────────────────────────

    def _run_rule_engine(self, features: list[dict]) -> list[dict]:
        return calculate_risk(features)

    def _run_ml_engine(self, features: list[dict]) -> list[dict]:
        if len(features) < 2:
            # IsolationForest needs at least 2 samples — return neutral scores
            return [
                {"api_key": f["api_key"], "anomaly_score": 50.0, "prediction": "normal"}
                for f in features
            ]
        try:
            return detect_anomalies(features)
        except Exception:
            return [
                {"api_key": f["api_key"], "anomaly_score": 50.0, "prediction": "normal"}
                for f in features
            ]
