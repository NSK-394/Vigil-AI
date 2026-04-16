import sys
if sys.stdout.encoding.lower() != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

from simulator import generate_logs
from feature_extractor import extract_features
from risk_engine import calculate_risk
from detector import detect_anomalies
from final_decision import combine_results
from storage import save_logs, save_features, save_results

logs = generate_logs(200)
features = extract_features(logs)
risk = calculate_risk(features)
ml = detect_anomalies(features)
final = combine_results(risk, ml)

# Save everything
save_logs(logs, "data/logs.csv")
save_features(features, "data/features.csv")
save_results(final, "data/final_results.csv")

print("Data saved successfully 🚀")