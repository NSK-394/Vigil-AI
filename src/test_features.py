from simulator import generate_logs
from feature_extractor import extract_features

logs = generate_logs(200)

features = extract_features(logs)

for f in features:
    print(f)