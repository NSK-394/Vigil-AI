"""
Confidence scoring for each detection engine.

Converts raw 0-100 scores into a 0.0-1.0 confidence value
that reflects how certain the engine is about its signal.

Key insight: scores near 0 or 100 are unambiguous (high confidence).
Scores near 50 are in the grey zone (low confidence — could go either way).
This is used by DecisionAgent to weight each engine's vote proportionally.
"""


def compute_confidence(score: float, engine: str = "generic") -> float:
    """
    Maps a raw score (0-100) to a confidence value (0.0-1.0).

    Distance from the ambiguous midpoint (50) determines confidence:
        score=100  -> confidence=1.0  (certain threat)
        score=0    -> confidence=1.0  (certain clean)
        score=50   -> confidence=0.0  (total ambiguity)

    Args:
        score:  Raw engine score in [0, 100].
        engine: Label for logging/debugging only.

    Returns:
        Confidence in [0.0, 1.0], rounded to 3 decimal places.
    """
    score = max(0.0, min(100.0, float(score)))
    confidence = abs(score - 50.0) / 50.0
    return round(confidence, 3)


def weighted_fusion(
    rule_score: float,
    ml_score: float,
    rule_conf: float,
    ml_conf: float,
    velocity_boost: float = 0.0,
    repeat_boost: float = 0.0,
) -> tuple[float, float]:
    """
    Fuse two engine scores using confidence as weights.
    Returns (fused_score, overall_confidence).

    If both confidences are 0 (both engines completely uncertain),
    falls back to a straight average to avoid division by zero.

    Args:
        rule_score:     Rule engine raw score (0-100).
        ml_score:       ML engine raw score (0-100).
        rule_conf:      Rule engine confidence (0.0-1.0).
        ml_conf:        ML engine confidence (0.0-1.0).
        velocity_boost: Extra score points for sudden request velocity spike.
        repeat_boost:   Extra score points for known repeat offenders.

    Returns:
        (fused_score clamped to [0,100], overall_confidence in [0.0,1.0])
    """
    total_weight = rule_conf + ml_conf

    if total_weight < 1e-9:
        # Both engines uncertain — equal weight fallback
        fused = (rule_score + ml_score) / 2.0
    else:
        fused = (rule_score * rule_conf + ml_score * ml_conf) / total_weight

    # Memory-derived signal boosts applied after fusion
    fused += velocity_boost + repeat_boost
    fused = max(0.0, min(100.0, fused))

    overall_conf = round((rule_conf + ml_conf) / 2.0, 3)
    return round(fused, 2), overall_conf


def label_from_score(fused_score: float) -> str:
    """
    Convert a fused 0-100 score to a verdict label.
    Thresholds are intentionally asymmetric: easier to reach HIGH
    than to stay LOW, matching a security-first posture.

        >= 65  -> HIGH
        >= 35  -> MEDIUM
        <  35  -> LOW
    """
    if fused_score >= 65:
        return "HIGH"
    elif fused_score >= 35:
        return "MEDIUM"
    return "LOW"
