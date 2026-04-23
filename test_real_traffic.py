"""
test_real_traffic.py — End-to-end validation of the real-traffic pipeline.

Run from project root:
    python test_real_traffic.py

Three test groups:
  1. Middleware Capture  — VigilMiddleware(direct=True) pushes logs to live_queue
  2. Detection E2E       — crafted real-traffic logs are detected by AgentLoop
  3. Alert Mock          — BLOCK action triggers both Slack and email alert functions

All tests run in-process (no live servers required).
Exits with code 1 if any check fails.
"""

import os
import sys
import tempfile

# ── sys.path: src/ must be importable before any project imports ─────────────
_root = os.path.dirname(os.path.abspath(__file__))
_src  = os.path.join(_root, "src")
for _p in (_src, _root):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# ─────────────────────────────────────────────────────────────────────────────

_results: list[tuple[bool, str]] = []


def check(condition: bool, description: str) -> None:
    status = "[PASS]" if condition else "[FAIL]"
    print(f"  {status}  {description}")
    _results.append((condition, description))


def section(title: str) -> None:
    print(f"\n{'='*62}")
    print(f"  {title}")
    print(f"{'='*62}")


# ── Test 1: Middleware Capture ────────────────────────────────────────────────

def test_middleware_capture() -> None:
    section("Test 1 — Middleware Capture (direct mode)")

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from middleware.fastapi_middleware import VigilMiddleware
    from live_queue import drain, push

    # Clear any leftover state from a previous run
    drain(99999)

    app = FastAPI()
    app.add_middleware(VigilMiddleware, direct=True)

    @app.get("/api/products")
    def products():
        return {"items": []}

    @app.get("/api/login")
    def login():
        return {"token": "fake"}

    client = TestClient(app, raise_server_exceptions=False)

    # Send 5 requests with the same api_key
    for _ in range(5):
        client.get("/api/products", headers={"x-api-key": "mw_test_key_001"})

    logs = drain(100)

    check(len(logs) == 5,
          f"Middleware pushed 5 logs into live_queue (got {len(logs)})")
    check(all(l.get("api_key") == "mw_test_key_001" for l in logs),
          "All logs carry the correct api_key")
    check(all(l.get("attack_type") == "real" for l in logs),
          "All logs have attack_type='real'")
    check(all("endpoint" in l for l in logs),
          "All logs include the endpoint field")
    check(all("response_time" in l or "latency" in l for l in logs),
          "All logs include timing field")

    # Sliding-window counter: last log should have request_count == 5
    last_count = logs[-1].get("request_count", 0)
    check(last_count == 5,
          f"Sliding-window counter: last log has request_count=5 (got {last_count})")

    # Bearer token extraction
    drain(99999)
    client.get("/api/login", headers={"Authorization": "Bearer bearer_key_999"})
    bearer_logs = drain(100)
    check(
        len(bearer_logs) == 1 and bearer_logs[0].get("api_key") == "bearer_key_999",
        "Bearer token extracted correctly as api_key",
    )

    # Query param fallback
    drain(99999)
    client.get("/api/products?api_key=query_key_777")
    qp_logs = drain(100)
    check(
        len(qp_logs) == 1 and qp_logs[0].get("api_key") == "query_key_777",
        "api_key query param extracted correctly",
    )

    # /health should be skipped (no log pushed)
    @app.get("/health")
    def health_ep():
        return {"ok": True}

    drain(99999)
    client.get("/health")
    health_logs = drain(100)
    check(len(health_logs) == 0,
          "/health endpoint is not logged (skip path)")

    drain(99999)  # clean up for next test
    print("  Test 1 done.")


# ── Test 2: Detection End-to-End ──────────────────────────────────────────────

def test_detection_e2e() -> None:
    section("Test 2 — Detection End-to-End (real traffic mode)")

    from live_queue import drain, push
    from core.agent_loop import AgentLoop

    drain(99999)
    os.makedirs(os.path.join(_root, "data", "memory"), exist_ok=True)

    # 50 normal logs — 10 distinct keys, 4 endpoints, low request counts
    NORMAL_ENDPOINTS = ["/api/user", "/api/products", "/api/orders", "/api/search"]
    for i in range(50):
        push({
            "api_key":       f"normal_key_{i % 10:03d}",
            "endpoint":      NORMAL_ENDPOINTS[i % len(NORMAL_ENDPOINTS)],
            "method":        "GET",
            "status":        200,
            "latency":       0.05,
            "ip_address":    f"10.0.0.{(i % 254) + 1}",
            "timestamp":     "2026-04-23 12:00:00",
            "request_count": (i % 5) + 1,   # 1–5, low and varied
            "attack_type":   "real",
        })

    # 20 attack logs — single key, single endpoint, sliding-window counts [1..20]
    ATTACK_KEY = "attack_key_001"
    for i in range(1, 21):
        push({
            "api_key":       ATTACK_KEY,
            "endpoint":      "/api/login",
            "method":        "POST",
            "status":        401,
            "latency":       0.02,
            "ip_address":    "45.33.100.200",
            "timestamp":     "2026-04-23 12:00:01",
            "request_count": i,   # simulates middleware sliding-window output
            "attack_type":   "real",
        })

    with tempfile.TemporaryDirectory() as tmp:
        loop = AgentLoop(
            ltm_path     = os.path.join(tmp, "ltm.json"),
            results_path = os.path.join(tmp, "results.csv"),
        )
        result = loop.run(source="real", n_logs=500)

    decisions = result.get("decisions", [])
    alerts    = result.get("alerts",    [])
    stats     = result.get("stats",     {})

    check(len(decisions) > 0,
          f"AgentLoop produced decisions (got {len(decisions)})")

    attack_decision = next(
        (d for d in decisions if d["api_key"] == ATTACK_KEY), None
    )

    check(attack_decision is not None,
          f"Attack key '{ATTACK_KEY}' appears in decisions")

    if attack_decision:
        label = attack_decision.get("final_label", "")
        check(label in ("HIGH", "MEDIUM"),
              f"Attack key detected as HIGH or MEDIUM (got '{label}')")

        reasoning = attack_decision.get("reasoning", "")
        check(len(reasoning) > 20,
              f"Reasoning trace is non-empty ({len(reasoning)} chars)")

        check("[" in reasoning,
              "Reasoning trace has standard header format")

        action = attack_decision.get("action", "")
        check(action in ("BLOCK", "RATE_LIMIT"),
              f"Attack key gets BLOCK or RATE_LIMIT action (got '{action}')")

    check(stats.get("total_keys", 0) > 0,
          f"Stats: total_keys > 0 (got {stats.get('total_keys')})")

    fired = stats.get("alerts_fired", 0)
    check(fired > 0,
          f"At least one alert fired (got {fired})")

    print(f"\n  Attack detection summary:")
    if attack_decision:
        print(f"    Label     : {attack_decision.get('final_label')}")
        print(f"    Action    : {attack_decision.get('action')}")
        print(f"    Fused     : {attack_decision.get('fused_score')}")
        print(f"    Confidence: {attack_decision.get('confidence'):.0%}")
        print(f"    Reasoning : {attack_decision.get('reasoning')}")

    print("  Test 2 done.")


# ── Test 3: Alert Mock ────────────────────────────────────────────────────────

def test_alert_mock() -> None:
    section("Test 3 — Alert Mock (BLOCK triggers Slack + email)")

    from unittest.mock import patch
    from agents.response_agent import ResponseAgent
    from memory.long_term import LongTermMemory

    with tempfile.TemporaryDirectory() as tmp:
        ltm   = LongTermMemory(path=os.path.join(tmp, "ltm.json"))
        agent = ResponseAgent(ltm)

        # Synthetic HIGH decision that will trigger BLOCK
        decisions = [{
            "api_key":       "mock_attack_key",
            "action":        "BLOCK",
            "final_label":   "HIGH",
            "fused_score":   92.0,
            "confidence":    0.88,
            "risk_score":    90,
            "anomaly_score": 85.0,
            "action_reason": "HIGH-risk verdict requires immediate containment",
            "reasoning":     "[HIGH | conf=88% | fused=92.0] — rule engine: high-volume (score 90).",
            "summary":       "rule score 90",
        }]
        features = [{
            "api_key":            "mock_attack_key",
            "average_requests":   85.0,
            "total_requests":     85,
            "unique_endpoints":   1,
            "request_variance":   200.0,
            "request_velocity":   0.0,
            "historical_avg":     10.0,
            "baseline_deviation": 750.0,
            "repeat_offender":    False,
            "prior_observations": 0,
        }]

        slack_calls: list = []
        email_calls: list = []

        # Patch names in response_agent's namespace (from alert_system import ...)
        with patch("agents.response_agent.send_slack_alert",
                   side_effect=lambda *a, **kw: slack_calls.append(a)):
            with patch("agents.response_agent.send_email_alert",
                       side_effect=lambda *a, **kw: email_calls.append(a)):
                agent.act(decisions, features,
                          results_path=os.path.join(tmp, "results.csv"))

        check(len(slack_calls) == 1,
              f"send_slack_alert called exactly once (got {len(slack_calls)})")
        check(len(email_calls) == 1,
              f"send_email_alert called exactly once (got {len(email_calls)})")

        if slack_calls:
            verdict, key, reason = slack_calls[0]
            check(verdict == "HIGH",
                  f"Slack alert: verdict='HIGH' (got '{verdict}')")
            check(key == "mock_attack_key",
                  f"Slack alert: key='mock_attack_key' (got '{key}')")
            check(len(reason) > 10,
                  "Slack alert: reasoning string is non-empty")

        if email_calls:
            verdict, key, _ = email_calls[0]
            check(verdict == "HIGH",
                  f"Email alert: verdict='HIGH' (got '{verdict}')")
            check(key == "mock_attack_key",
                  f"Email alert: key='mock_attack_key' (got '{key}')")

        # LOG action must NOT trigger alerts
        log_decisions = [{
            "api_key":       "low_risk_key",
            "action":        "LOG",
            "final_label":   "LOW",
            "fused_score":   12.0,
            "confidence":    0.20,
            "risk_score":    10,
            "anomaly_score": 30.0,
            "action_reason": "LOW-risk — recorded for baseline only",
            "reasoning":     "[LOW | conf=20% | fused=12.0] — no signals.",
            "summary":       "normal",
        }]
        log_features = [{
            "api_key":            "low_risk_key",
            "average_requests":   2.0,
            "total_requests":     2,
            "unique_endpoints":   3,
            "request_variance":   0.5,
            "request_velocity":   0.0,
            "historical_avg":     2.0,
            "baseline_deviation": 0.0,
            "repeat_offender":    False,
            "prior_observations": 1,
        }]

        slack_log_calls: list = []
        email_log_calls: list = []
        ltm2 = LongTermMemory(path=os.path.join(tmp, "ltm2.json"))
        agent2 = ResponseAgent(ltm2)

        with patch("agents.response_agent.send_slack_alert",
                   side_effect=lambda *a, **kw: slack_log_calls.append(a)):
            with patch("agents.response_agent.send_email_alert",
                       side_effect=lambda *a, **kw: email_log_calls.append(a)):
                agent2.act(log_decisions, log_features,
                           results_path=os.path.join(tmp, "results_low.csv"))

        check(len(slack_log_calls) == 0,
              "LOG action does NOT trigger Slack alert")
        check(len(email_log_calls) == 0,
              "LOG action does NOT trigger email alert")

    print("  Test 3 done.")


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(os.path.join(_root, "data", "memory"), exist_ok=True)

    test_middleware_capture()
    test_detection_e2e()
    test_alert_mock()

    total  = len(_results)
    passed = sum(1 for ok, _ in _results if ok)
    failed = total - passed

    print(f"\n{'='*62}")
    print(f"  Results: {passed}/{total} passed   ({failed} failed)")
    print(f"{'='*62}\n")

    if failed:
        sys.exit(1)
