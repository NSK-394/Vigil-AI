"""
Phase 2 verification — run from src/ directory:
    python test_core.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from core.confidence import compute_confidence, weighted_fusion, label_from_score
from core.explainer  import build_reasoning, build_short_summary, explain_action


# ── Confidence tests ──────────────────────────────────────────────────────

def test_confidence_scores():
    print("\n=== compute_confidence ===")

    cases = [
        (100,  1.0,  "certain threat"),
        (0,    1.0,  "certain clean"),
        (50,   0.0,  "total ambiguity"),
        (75,   0.5,  "mid-high threat"),
        (25,   0.5,  "mid-low"),
        (90,   0.8,  "strong threat"),
    ]
    for score, expected, label in cases:
        got = compute_confidence(score)
        assert abs(got - expected) < 0.01, f"FAIL {label}: got {got}, expected {expected}"
        print(f"  score={score:3d} -> conf={got:.3f}  ({label})")

    # Clamping
    assert compute_confidence(-10) == compute_confidence(0)
    assert compute_confidence(110) == compute_confidence(100)
    print("  Clamping: OK")
    print("  PASS")


def test_weighted_fusion():
    print("\n=== weighted_fusion ===")

    # Both engines agree HIGH — should produce high fused score
    fs, oc = weighted_fusion(90, 85, 0.8, 0.7)
    print(f"  Both HIGH: fused={fs}, conf={oc}")
    assert fs > 70, f"Expected >70, got {fs}"
    assert oc > 0.5

    # Rule says HIGH (conf=0.9), ML uncertain (conf=0.1) — rule dominates
    fs2, _ = weighted_fusion(80, 50, 0.9, 0.1)
    print(f"  Rule dominates: fused={fs2}")
    assert fs2 > 70, f"Rule-dominant fusion failed: {fs2}"

    # Both engines uncertain — fallback to average
    fs3, oc3 = weighted_fusion(60, 40, 0.0, 0.0)
    print(f"  Zero-conf fallback: fused={fs3} (expected 50.0)")
    assert fs3 == 50.0

    # Velocity boost pushes MEDIUM into HIGH zone
    fs4, _ = weighted_fusion(55, 55, 0.3, 0.3, velocity_boost=15)
    print(f"  Velocity boost: fused={fs4}")
    assert fs4 > 65, f"Boost failed: {fs4}"

    # Score clamped to 100
    fs5, _ = weighted_fusion(100, 100, 1.0, 1.0, velocity_boost=20, repeat_boost=20)
    assert fs5 == 100.0, f"Clamp failed: {fs5}"
    print("  Clamp at 100: OK")

    print("  PASS")


def test_label_from_score():
    print("\n=== label_from_score ===")
    assert label_from_score(70)  == "HIGH"
    assert label_from_score(65)  == "HIGH"
    assert label_from_score(64)  == "MEDIUM"
    assert label_from_score(35)  == "MEDIUM"
    assert label_from_score(34)  == "LOW"
    assert label_from_score(0)   == "LOW"
    print("  Thresholds: OK")
    print("  PASS")


# ── Explainer tests ───────────────────────────────────────────────────────

def test_build_reasoning():
    print("\n=== build_reasoning ===")

    # Case 1: Full HIGH — all signals firing
    d_high = {
        "risk_score":        92,
        "anomaly_score":     85.0,
        "ml_prediction":     "anomaly",
        "request_velocity":  70,
        "repeat_offender":   True,
        "baseline_deviation": 120.0,
    }
    r = build_reasoning(d_high, "HIGH", 91.5, 0.82)
    print(f"  HIGH trace:\n    {r}")
    assert "[HIGH | conf=82% | fused=91.5]" in r
    assert "rule engine" in r
    assert "ML" in r
    assert "velocity spike" in r
    assert "repeat offender" in r
    assert "baseline" in r

    # Case 2: Clean LOW — no signals
    d_low = {
        "risk_score":        10,
        "anomaly_score":     12.0,
        "ml_prediction":     "normal",
        "request_velocity":  2,
        "repeat_offender":   False,
        "baseline_deviation": 5.0,
    }
    r2 = build_reasoning(d_low, "LOW", 11.0, 0.78)
    print(f"  LOW trace:\n    {r2}")
    assert "baseline behavior" in r2
    assert "[LOW | conf=78% | fused=11.0]" in r2

    # Case 3: MEDIUM — only rule engine, no ML or memory signal
    d_mid = {
        "risk_score":        55,
        "anomaly_score":     30.0,
        "ml_prediction":     "normal",
        "request_velocity":  5,
        "repeat_offender":   False,
        "baseline_deviation": 10.0,
    }
    r3 = build_reasoning(d_mid, "MEDIUM", 48.0, 0.30)
    print(f"  MEDIUM trace:\n    {r3}")
    assert "rule engine" in r3

    print("  PASS")


def test_build_short_summary():
    print("\n=== build_short_summary ===")

    s1 = build_short_summary({"repeat_offender": True, "request_velocity": 0, "risk_score": 0, "anomaly_score": 0, "ml_prediction": "normal"}, "HIGH")
    assert s1 == "repeat offender"

    s2 = build_short_summary({"repeat_offender": False, "request_velocity": 60, "risk_score": 0, "anomaly_score": 0, "ml_prediction": "normal"}, "HIGH")
    assert "velocity spike" in s2

    s3 = build_short_summary({"repeat_offender": False, "request_velocity": 0, "risk_score": 80, "anomaly_score": 0, "ml_prediction": "normal"}, "HIGH")
    assert "rule score" in s3

    s4 = build_short_summary({"repeat_offender": False, "request_velocity": 0, "risk_score": 10, "anomaly_score": 0, "ml_prediction": "normal"}, "LOW")
    assert s4 == "normal"

    print(f"  Repeat offender  -> '{s1}'")
    print(f"  Velocity spike   -> '{s2}'")
    print(f"  Rule score       -> '{s3}'")
    print(f"  Normal           -> '{s4}'")
    print("  PASS")


def test_explain_action():
    print("\n=== explain_action ===")

    a1 = explain_action("BLOCK", "HIGH", repeat_offender=False)
    a2 = explain_action("BLOCK", "HIGH", repeat_offender=True)
    a3 = explain_action("RATE_LIMIT", "MEDIUM", repeat_offender=False)
    a4 = explain_action("LOG", "LOW", repeat_offender=False)

    print(f"  BLOCK (new)      : {a1}")
    print(f"  BLOCK (repeat)   : {a2}")
    print(f"  RATE_LIMIT       : {a3}")
    print(f"  LOG              : {a4}")

    assert "containment" in a1
    assert "repeat offender" in a2
    assert "throttling" in a3
    assert "baseline" in a4

    print("  PASS")


if __name__ == "__main__":
    test_confidence_scores()
    test_weighted_fusion()
    test_label_from_score()
    test_build_reasoning()
    test_build_short_summary()
    test_explain_action()
    print("\n[Phase 2] All core tests passed.\n")
