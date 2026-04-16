"""
Master integration test — validates all 5 phases end-to-end.
Run from project root:
    .venv/Scripts/python src/test_integration.py
"""

import sys, os, json, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from memory.short_term      import ShortTermMemory
from memory.long_term       import LongTermMemory
from agents.monitor_agent   import MonitorAgent
from agents.detection_agent import DetectionAgent
from agents.decision_agent  import DecisionAgent
from agents.response_agent  import ResponseAgent
from core.agent_loop        import AgentLoop
from core.confidence        import compute_confidence, weighted_fusion, label_from_score
from core.explainer         import build_reasoning, build_short_summary, explain_action


PASS = "[PASS]"
FAIL = "[FAIL]"


def section(title: str) -> None:
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def check(condition: bool, description: str) -> None:
    status = PASS if condition else FAIL
    print(f"  {status}  {description}")
    if not condition:
        raise AssertionError(f"FAILED: {description}")


# ── Phase 1: Memory ──────────────────────────────────────────────────────

def test_phase1_memory() -> None:
    section("Phase 1 — Memory System")

    stm = ShortTermMemory(window=5)
    for i, v in enumerate([10, 20, 40, 80]):
        stm.record("key_A", {"average_requests": float(v)})
    check(stm.velocity("key_A", "average_requests") == 70.0, "STM velocity = 70")
    check(abs(stm.avg("key_A", "average_requests") - 37.5) < 0.01, "STM rolling avg = 37.5")
    check(len(stm.get("key_A")) == 4, "STM window length = 4")

    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "ltm.json")
        ltm  = LongTermMemory(path=path)
        for _ in range(5):
            ltm.update("key_B", {"average_requests": 20.0}, "LOW")
        check(not ltm.is_repeat_offender("key_B"), "LTM: 0 HIGHs — not repeat offender")
        for _ in range(3):
            ltm.update("key_B", {"average_requests": 90.0}, "HIGH")
        check(ltm.is_repeat_offender("key_B"), "LTM: 3 HIGHs — repeat offender")
        check(ltm.deviation_from_baseline("key_B", 90.0) > 0, "LTM: deviation > 0")

        ltm2 = LongTermMemory(path=path)
        check(ltm2.is_repeat_offender("key_B"), "LTM: survives reload from disk")

    print("  Phase 1 OK")


# ── Phase 2: Confidence + Explainer ──────────────────────────────────────

def test_phase2_core() -> None:
    section("Phase 2 — Confidence & Explainer")

    check(compute_confidence(100) == 1.0, "conf(100) = 1.0")
    check(compute_confidence(50)  == 0.0, "conf(50)  = 0.0")
    check(compute_confidence(0)   == 1.0, "conf(0)   = 1.0")

    fused, conf = weighted_fusion(90, 85, 0.8, 0.7)
    check(fused > 80, f"fusion(90,85,0.8,0.7) fused={fused} > 80")
    fused2, _ = weighted_fusion(60, 40, 0.0, 0.0)
    check(fused2 == 50.0, "zero-conf fallback = 50.0")

    check(label_from_score(70) == "HIGH",   "label(70) = HIGH")
    check(label_from_score(50) == "MEDIUM", "label(50) = MEDIUM")
    check(label_from_score(20) == "LOW",    "label(20) = LOW")

    d = {"risk_score": 92, "anomaly_score": 85.0, "ml_prediction": "anomaly",
         "request_velocity": 70, "repeat_offender": True, "baseline_deviation": 120.0}
    r = build_reasoning(d, "HIGH", 91.5, 0.82)
    check("[HIGH | conf=82% | fused=91.5]" in r, "reasoning: header correct")
    check("rule engine"      in r, "reasoning: rule engine clause")
    check("ML"               in r, "reasoning: ML clause")
    check("velocity spike"   in r, "reasoning: velocity clause")
    check("repeat offender"  in r, "reasoning: repeat-offender clause")

    s = build_short_summary({"repeat_offender": True, "request_velocity": 0,
                             "risk_score": 0, "anomaly_score": 0,
                             "ml_prediction": "normal"}, "HIGH")
    check(s == "repeat offender", f"short summary = 'repeat offender', got '{s}'")

    ar = explain_action("BLOCK", "HIGH", repeat_offender=False)
    check("containment" in ar, "explain_action: BLOCK reason mentions containment")

    print("  Phase 2 OK")


# ── Phase 3: Four Agents ─────────────────────────────────────────────────

def test_phase3_agents() -> None:
    section("Phase 3 — Agent Components")

    with tempfile.TemporaryDirectory() as tmp:
        stm = ShortTermMemory(window=10)
        ltm = LongTermMemory(path=os.path.join(tmp, "ltm.json"))

        # MonitorAgent
        mon  = MonitorAgent(stm, ltm)
        feats, logs = mon.observe(n_logs=80)
        check(len(logs) == 80,   "MonitorAgent: 80 logs generated")
        check(len(feats) > 0,    "MonitorAgent: features extracted")
        check("request_velocity" in feats[0], "MonitorAgent: velocity field present")
        check("repeat_offender"  in feats[0], "MonitorAgent: repeat_offender field present")
        check("baseline_deviation" in feats[0], "MonitorAgent: deviation field present")

        # Traffic mix override
        atk_feats, atk_logs = mon.observe(
            n_logs=60, traffic_mix={"normal":0.1,"brute_force":0.5,"scraping":0.3,"ddos":0.1})
        atk_share = sum(1 for l in atk_logs if l["attack_type"] != "normal") / len(atk_logs)
        check(atk_share > 0.7, f"MonitorAgent: traffic mix override works ({atk_share:.0%} attack)")

        # DetectionAgent
        det = DetectionAgent()
        dets = det.analyze(feats)
        check(len(dets) == len(feats), "DetectionAgent: one detection per feature")
        check(all(0 <= d["rule_confidence"] <= 1 for d in dets), "DetectionAgent: conf in [0,1]")
        check(dets == sorted(dets, key=lambda x: x["risk_score"], reverse=True),
              "DetectionAgent: sorted by risk_score desc")
        single = det.analyze(feats[:1])
        check(single[0]["anomaly_score"] == 50.0, "DetectionAgent: single-row ML fallback = 50")

        # DecisionAgent
        dec  = DecisionAgent()
        decs = dec.decide(dets)
        check(len(decs) == len(dets), "DecisionAgent: one decision per detection")
        check(all(d["final_label"] in ("HIGH","MEDIUM","LOW") for d in decs),
              "DecisionAgent: labels valid")
        check(all(d["action"] in ("BLOCK","RATE_LIMIT","ALERT","LOG") for d in decs),
              "DecisionAgent: actions valid")
        check(all(d["final_label"] != "HIGH" or d["action"] == "BLOCK" for d in decs),
              "DecisionAgent: HIGH always BLOCK")
        check(all("[" in d["reasoning"] for d in decs), "DecisionAgent: reasoning has header")

        # Repeat-offender escalation
        synthetic = [{
            "api_key": "repeat_test", "risk_score": 55, "anomaly_score": 40.0,
            "rule_label": "MEDIUM", "ml_prediction": "normal",
            "rule_confidence": 0.1, "ml_confidence": 0.2,
            "request_velocity": 0.0, "baseline_deviation": 0.0,
            "repeat_offender": True, "prior_observations": 5,
            "total_requests": 200, "average_requests": 55.0, "unique_endpoints": 2,
        }]
        esc = dec.decide(synthetic)
        check(esc[0]["action"] == "BLOCK", "DecisionAgent: repeat-offender MEDIUM -> BLOCK")

        # ResponseAgent
        results_path = os.path.join(tmp, "results.csv")
        res = ResponseAgent(ltm)
        alerts = res.act(decs, feats, results_path)
        check(os.path.exists(results_path), "ResponseAgent: results.csv written")
        check(all(a["action"] != "LOG" for a in alerts), "ResponseAgent: LOG not in alerts")
        check(all("reasoning" in a for a in alerts), "ResponseAgent: reasoning in alerts")

    print("  Phase 3 OK")


# ── Phase 4: Full AgentLoop ───────────────────────────────────────────────

def test_phase4_loop() -> None:
    section("Phase 4 — AgentLoop (Full Cycle)")

    with tempfile.TemporaryDirectory() as tmp:
        loop = AgentLoop(
            ltm_path=os.path.join(tmp, "ltm.json"),
            results_path=os.path.join(tmp, "results.csv"),
        )

        # Normal cycle
        r1 = loop.run(n_logs=80,
                      traffic_mix={"normal":0.9,"brute_force":0.03,
                                   "scraping":0.05,"ddos":0.02})
        check("decisions" in r1 and "alerts" in r1 and "stats" in r1,
              "Loop: result has all keys")
        check(r1["cycle"] == 1, "Loop: cycle counter = 1")
        check(r1["stats"]["total_keys"] > 0, "Loop: keys monitored > 0")

        # Attack cycle — should produce more HIGHs
        r2 = loop.run(n_logs=80,
                      traffic_mix={"normal":0.1,"brute_force":0.4,
                                   "scraping":0.3,"ddos":0.2})
        check(r2["cycle"] == 2, "Loop: cycle counter = 2")
        check(r2["stats"]["high"] >= r1["stats"]["high"],
              f"Loop: attack cycle HIGH ({r2['stats']['high']}) >= normal ({r1['stats']['high']})")

        # Artefacts written
        check(os.path.exists(os.path.join(tmp, "results.csv")), "Loop: results.csv exists")
        check(os.path.exists(os.path.join(tmp, "ltm.json")),    "Loop: long_term.json exists")

        with open(os.path.join(tmp, "ltm.json")) as f:
            ltm_data = json.load(f)
        check(len(ltm_data) > 0, f"Loop: LTM has {len(ltm_data)} keys after 2 cycles")

        # All decisions have reasoning
        for d in r2["decisions"]:
            check(len(d["reasoning"]) > 20, f"Loop: reasoning non-empty for {d['api_key']}")
            break  # spot-check first only

        # Confidence stat present and valid
        conf = r2["stats"]["avg_confidence"]
        check(0.0 <= conf <= 1.0, f"Loop: avg_confidence={conf:.3f} in [0,1]")

    print("  Phase 4 OK")


# ── Phase 5: Artefacts ────────────────────────────────────────────────────

def test_phase5_artefacts() -> None:
    section("Phase 5 — Project Artefacts")

    root = os.path.join(os.path.dirname(__file__), "..")

    check(os.path.exists(os.path.join(root, "requirements.txt")), "requirements.txt exists")
    check(os.path.exists(os.path.join(root, ".gitignore")),       ".gitignore exists")
    check(os.path.exists(os.path.join(root, "run_agent.py")),     "run_agent.py exists")
    check(os.path.exists(os.path.join(root, "README.md")),        "README.md exists")

    with open(os.path.join(root, "requirements.txt")) as f:
        reqs = f.read()
    for pkg in ["streamlit", "scikit-learn", "pandas", "numpy"]:
        check(pkg in reqs, f"requirements.txt contains {pkg}")

    with open(os.path.join(root, ".gitignore")) as f:
        gi = f.read()
    check("data/memory/" in gi or "long_term.json" in gi, ".gitignore covers memory files")
    check(".venv"         in gi, ".gitignore covers .venv")

    print("  Phase 5 OK")


# ── Run all ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs("data/memory", exist_ok=True)

    test_phase1_memory()
    test_phase2_core()
    test_phase3_agents()
    test_phase4_loop()
    test_phase5_artefacts()

    print(f"\n{'='*60}")
    print("  ALL PHASES PASSED — VigilAI Agent System verified.")
    print(f"{'='*60}\n")
