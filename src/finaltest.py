from simulator import generate_logs
from feature_extractor import extract_features
from risk_engine import calculate_risk
from detector import detect_anomalies
from final_decision import combine_results

logs = generate_logs(200)

features = extract_features(logs)
risk = calculate_risk(features)
ml = detect_anomalies(features)

final = combine_results(risk, ml)

for f in final:
    print(f)