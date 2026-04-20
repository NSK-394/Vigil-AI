"""
core/confidence.py — Confidence scoring and weighted engine fusion.

Converts raw 0-100 engine scores into confidence values, then blends
the two engine signals proportionally to their certainty.

Key insight: a score of 50 is maximally ambiguous (conf=0.0); scores
near 0 or 100 are unambiguous (conf=1.0). This prevents uncertain
engines from corrupting a confident engine's clear verdict.
"""


def compute_confidence(score: float, engine: str = "generic") -> float:
    """
    Map a raw engine score (0–100) to a confidence value (0.0–1.0).

    Distance from the ambiguous midpoint (50) determines confidence:
        score = 100 or 0 → confidence = 1.0
        score = 50       → confidence = 0.0
    """
    score = max(0.0, min(100.0, float(score)))
    return round(abs(score - 50.0) / 50.0, 3)


def weighted_fusion(
    rule_score:     float,
    ml_score:       float,
    rule_conf:      float,
    ml_conf:        float,
    velocity_boost: float = 0.0,
    repeat_boost:   float = 0.0,
) -> tuple[float, float]:
    """
    Fuse two engine scores using their confidence values as weights.

    Falls back to a straight average when both confidences are zero.
    Memory-derived boosts (velocity, repeat-offender) are applied after fusion.

    Returns:
        (fused_score clamped to [0, 100], overall_confidence in [0.0, 1.0])
    """
    total_weight = rule_conf + ml_conf
    fused = (
        (rule_score * rule_conf + ml_score * ml_conf) / total_weight
        if total_weight > 1e-9
        else (rule_score + ml_score) / 2.0
    )
    fused = max(0.0, min(100.0, fused + velocity_boost + repeat_boost))
    return round(fused, 2), round((rule_conf + ml_conf) / 2.0, 3)


def label_from_score(fused_score: float) -> str:
    """
    Convert a fused score to a verdict label using security-first thresholds:
        >= 65 → HIGH  (easier to reach — prefer fewer false negatives)
        >= 35 → MEDIUM
        <  35 → LOW
    """
    if fused_score >= 65:
        return "HIGH"
    if fused_score >= 35:
        return "MEDIUM"
    return "LOW"
