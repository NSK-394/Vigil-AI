from simulator import generate_logs
from feature_extractor import extract_features
from detector import detect_anomalies

logs = generate_logs(200)
features = extract_features(logs)

results = detect_anomalies(features)

for r in results:
    print(r)