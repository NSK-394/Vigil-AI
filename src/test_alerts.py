"""
test_alerts.py
--------------
End-to-end test of the alert + blocking system.

Run from the project root:
    .venv\\Scripts\\python.exe src\\test_alerts.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from simulator         import generate_logs
from feature_extractor import extract_features
from risk_engine       import calculate_risk
from detector          import detect_anomalies
from final_decision    import combine_results
from alert_system      import generate_alerts, get_blocked_keys

# ── Run the full pipeline ─────────────────────────────────────────────────
print("\n[test_alerts] Running pipeline on 200 logs...\n")

logs     = generate_logs(200)
features = extract_features(logs)
risk     = calculate_risk(features)
ml       = detect_anomalies(features)
final    = combine_results(risk, ml)

# ── Generate alerts (also auto-blocks HIGH-risk keys) ────────────────────
alerts = generate_alerts(final)

print()

# ── Print each alert in the expected format ───────────────────────────────
if not alerts:
    print("✅ No HIGH-risk keys detected — system clear.")
else:
    for a in alerts:
        print(f"🚨 ALERT: {a['api_key']} is HIGH RISK "
              f"(Score: {a['risk_score']} | Anomaly: {a['anomaly_score']})")

# ── Print blocked keys ────────────────────────────────────────────────────
blocked = get_blocked_keys()
print(f"\n⛔ Blocked keys this session ({len(blocked)}):")
for key in blocked:
    print(f"   ⛔ {key}")

# ── System status ─────────────────────────────────────────────────────────
print()
if len(alerts) > 0:
    print("⚠️  SYSTEM UNDER ATTACK — automated blocking engaged.")
else:
    print("🟢 System nominal — no threats detected.")
