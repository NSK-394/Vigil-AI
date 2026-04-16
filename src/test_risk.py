from simulator import generate_logs
from feature_extractor import extract_features
from risk_engine import calculate_risk

logs = generate_logs(100)
features = extract_features(logs)
risks = calculate_risk(features)

for r in risks:
    print(r)