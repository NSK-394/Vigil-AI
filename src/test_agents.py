"""
Phase 3 integration test — run from project root:
    .venv/Scripts/python src/test_agents.py
"""

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

import tempfile, json
from pathlib import Path

from memory.short_term      import ShortTermMemory
from memory.long_term       import LongTermMemory
from agents.monitor_agent   import MonitorAgent
from agents.detection_agent import DetectionAgent
from agents.decision_agent  import DecisionAgent
from agents.response_agent  import ResponseAgent
from core.agent_loop        import AgentLoop


def section(title):
    print(f"\n=== {title} ===")


def test_monitor_agent():
    section("MonitorAgent")
    stm = ShortTermMemory(window=5)
    ltm = LongTermMemory(path="data/memory/test_ltm.json")

    agent = MonitorAgent(stm, ltm)
    features, logs = agent.observe(n_logs=80)

    assert len(logs) == 80,             f"Expected 80 logs, got {len(logs)}"
    assert len(features) > 0,           "No features extracted"

    sample = features[0]
    required = ["api_key", "average_requests", "request_velocity",
                "baseline_deviation", "repeat_offender", "prior_observations"]
    for field in required:
        assert field in sample, f"Missing field: {field}"

    print(f"  Logs generated    : {len(logs)}")
    print(f"  Keys extracted    : {len(features)}")
    print(f"  Sample key        : {sample['api_key']}")
    print(f"  Memory fields     : velocity={sample['request_velocity']}, "
          f"deviation={sample['baseline_deviation']}, "
          f"repeat={sample['repeat_offender']}")

    # Test custom traffic mix — should skew toward attacks
    atk_features, atk_logs = agent.observe(
        n_logs=60,
        traffic_mix={"normal": 0.1, "brute_force": 0.4,
                     "scraping": 0.3, "ddos": 0.2}
    )
    attack_logs = [l for l in atk_logs if l["attack_type"] != "normal"]
    assert len(attack_logs) > len(atk_logs) * 0.5, "Traffic mix override failed"
    print(f"  Custom mix attack%: {len(attack_logs)/len(atk_logs):.0%} (expected >50%)")

    # Cleanup
    Path("data/memory/test_ltm.json").unlink(missing_ok=True)
    print("  PASS")


def test_detection_agent():
    section("DetectionAgent")
    stm = ShortTermMemory(window=5)
    ltm = LongTermMemory(path="data/memory/test_ltm.json")
    monitor   = MonitorAgent(stm, ltm)
    detection = DetectionAgent()

    features, _ = monitor.observe(n_logs=100)
    detections  = detection.analyze(features)

    assert len(detections) == len(features), "Detection count mismatch"

    sample = detections[0]
    required = ["api_key", "risk_score", "anomaly_score", "rule_label",
                "ml_prediction", "rule_confidence", "ml_confidence",
                "request_velocity", "repeat_offender"]
    for field in required:
        assert field in sample, f"Missing field: {field}"

    # Confidences must be in [0, 1]
    for d in detections:
        assert 0.0 <= d["rule_confidence"] <= 1.0
        assert 0.0 <= d["ml_confidence"]   <= 1.0

    # Sorted by risk_score desc
    scores = [d["risk_score"] for d in detections]
    assert scores == sorted(scores, reverse=True), "Not sorted by risk_score"

    print(f"  Keys analyzed     : {len(detections)}")
    print(f"  Top key           : {sample['api_key']} "
          f"(risk={sample['risk_score']}, ml={sample['ml_prediction']}, "
          f"rule_conf={sample['rule_confidence']:.2f})")
    print(f"  Confidence range  : [{min(d['rule_confidence'] for d in detections):.2f}, "
          f"{max(d['rule_confidence'] for d in detections):.2f}]")

    # Edge case: single feature — ML must not crash
    single_feat = features[:1]
    single_det  = detection.analyze(single_feat)
    assert len(single_det) == 1
    assert single_det[0]["anomaly_score"] == 50.0, "Single-row fallback score wrong"
    print("  Single-row ML fallback: PASS")

    Path("data/memory/test_ltm.json").unlink(missing_ok=True)
    print("  PASS")


def test_decision_agent():
    section("DecisionAgent")
    stm = ShortTermMemory(window=5)
    ltm = LongTermMemory(path="data/memory/test_ltm.json")
    monitor   = MonitorAgent(stm, ltm)
    detection = DetectionAgent()
    decision  = DecisionAgent()

    features, _  = monitor.observe(n_logs=150)
    detections   = detection.analyze(features)
    decisions    = decision.decide(detections)

    assert len(decisions) == len(detections)

    required = ["final_label", "fused_score", "confidence",
                "action", "action_reason", "reasoning", "summary"]
    for field in required:
        assert field in decisions[0], f"Missing: {field}"

    # Labels valid
    for d in decisions:
        assert d["final_label"] in ("HIGH", "MEDIUM", "LOW")
        assert d["action"] in ("BLOCK", "RATE_LIMIT", "ALERT", "LOG")
        assert 0.0 <= d["confidence"] <= 1.0
        assert 0.0 <= d["fused_score"] <= 100.0

    # HIGH always gets BLOCK
    for d in decisions:
        if d["final_label"] == "HIGH":
            assert d["action"] == "BLOCK", f"HIGH key not BLOCK: {d['action']}"

    # Reasoning trace must include label header
    for d in decisions:
        assert f"[{d['final_label']}" in d["reasoning"], "Reasoning missing label header"

    labels = [d["final_label"] for d in decisions]
    print(f"  HIGH  : {labels.count('HIGH')}")
    print(f"  MEDIUM: {labels.count('MEDIUM')}")
    print(f"  LOW   : {labels.count('LOW')}")
    print(f"  Sample reasoning:")
    print(f"    {decisions[0]['reasoning'][:120]}...")

    # Repeat offender escalation test
    synthetic = [{
        "api_key":          "test_repeat",
        "risk_score":       55,
        "anomaly_score":    40.0,
        "rule_label":       "MEDIUM",
        "ml_prediction":    "normal",
        "rule_confidence":  0.1,
        "ml_confidence":    0.2,
        "request_velocity": 0.0,
        "baseline_deviation": 0.0,
        "repeat_offender":  True,
        "prior_observations": 10,
        "total_requests":   200,
        "average_requests": 55.0,
        "unique_endpoints": 2,
    }]
    result = decision.decide(synthetic)
    assert result[0]["action"] == "BLOCK", "Repeat offender not escalated to BLOCK"
    print("  Repeat offender escalation: PASS")

    Path("data/memory/test_ltm.json").unlink(missing_ok=True)
    print("  PASS")


def test_full_agent_loop():
    section("AgentLoop (full cycle)")

    with tempfile.TemporaryDirectory() as tmp:
        ltm_path     = os.path.join(tmp, "ltm.json")
        results_path = os.path.join(tmp, "results.csv")

        loop = AgentLoop(ltm_path=ltm_path, results_path=results_path)

        # Cycle 1 — normal traffic
        r1 = loop.run(n_logs=100,
                      traffic_mix={"normal": 0.9, "brute_force": 0.03,
                                   "scraping": 0.05, "ddos": 0.02})
        assert "decisions" in r1 and "alerts" in r1 and "stats" in r1
        assert r1["cycle"] == 1
        assert r1["stats"]["total_keys"] > 0

        # Cycle 2 — attack traffic
        r2 = loop.run(n_logs=100,
                      traffic_mix={"normal": 0.1, "brute_force": 0.4,
                                   "scraping": 0.3, "ddos": 0.2})
        assert r2["cycle"] == 2
        assert r2["stats"]["high"] >= r1["stats"]["high"], \
            "Attack cycle should have >= HIGH count than normal cycle"

        # Results CSV must exist
        assert os.path.exists(results_path), "results.csv not written"

        # LTM persisted
        assert os.path.exists(ltm_path), "long_term.json not written"
        with open(ltm_path) as f:
            ltm_data = json.load(f)
        assert len(ltm_data) > 0, "LTM empty after two cycles"

        print(f"  Cycle 1 stats: {r1['stats']}")
        print(f"  Cycle 2 stats: {r2['stats']}")
        print(f"  LTM keys after 2 cycles: {len(ltm_data)}")
        print(f"  Results CSV exists: {os.path.exists(results_path)}")

        # Decisions have reasoning in cycle 2
        for d in r2["decisions"][:3]:
            assert len(d["reasoning"]) > 20, "Reasoning too short"

        print(f"  Sample cycle-2 reasoning:")
        print(f"    {r2['decisions'][0]['reasoning'][:120]}...")

    print("  PASS")


if __name__ == "__main__":
    os.makedirs("data/memory", exist_ok=True)

    test_monitor_agent()
    test_detection_agent()
    test_decision_agent()
    test_full_agent_loop()

    print("\n[Phase 3] All agent tests passed.\n")
