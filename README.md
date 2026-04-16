# VigilAI — Autonomous Security Agent System

> **Real-Time API Threat Intelligence powered by an Agentic AI Loop**

VigilAI is an end-to-end autonomous security system that detects, reasons about, and responds to API abuse — without human intervention. Four specialized AI agents collaborate in a continuous loop, backed by persistent memory, to classify threats, generate auditable reasoning traces, and take prioritized response actions in real time.

---

## 🚀 Key Highlights

- **Agentic Architecture** — Four agents (Monitor → Detection → Decision → Response) run a continuous Observe → Reason → Decide → Act loop, not a one-shot pipeline
- **Dual-Engine Fusion** — IsolationForest (ML) and a rule-based scoring engine run in parallel; each vote is weighted by its own confidence before fusion
- **Persistent Memory** — Short-term sliding window detects burst velocity; long-term EMA baseline per key survives restarts and learns repeat offenders over time
- **Explainable Decisions** — Every verdict ships a structured reasoning trace explaining exactly which signals fired, why, and with what confidence — no black-box outputs
- **Adaptive Response** — The feedback loop updates behavioral baselines after every action; keys accumulating 3+ HIGH verdicts auto-escalate on future cycles
- **Production Parallels** — Architecture directly mirrors SIEM (IBM QRadar), SOAR (Splunk SOAR), and WAF (AWS WAF) systems used in enterprise SOC workflows

---

## What Makes This Agentic

Most detection systems are stateless pipelines: data goes in, a score comes out. VigilAI's agents are different:

| Capability | What it means |
|---|---|
| **Memory** | Short-term sliding window tracks burst velocity; long-term memory builds a per-key behavioral baseline that survives restarts |
| **Confidence scoring** | Every engine vote is weighted by how certain it is — a score of 50 carries zero weight |
| **Reasoning traces** | Every decision produces a human-readable explanation: which signals fired, why, with what confidence |
| **Feedback loop** | After each action, the agent updates long-term memory — the system learns repeat offenders over time |
| **Action prioritization** | BLOCK > RATE_LIMIT > ALERT > LOG — context-sensitive, not a fixed threshold |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              AGENT LOOP  (Observe → Reason → Decide → Act)      │
│                                                                 │
│   ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐  │
│   │  MONITOR     │    │  DETECTION      │    │  DECISION    │  │
│   │  AGENT       │───▶│  AGENT          │───▶│  AGENT       │  │
│   │              │    │  (parallel)     │    │              │  │
│   │  simulator   │    │  risk_engine    │    │  fusion +    │  │
│   │  feat_extract│    │  detector       │    │  reasoning   │  │
│   └──────┬───────┘    └────────┬────────┘    └──────┬───────┘  │
│          │                     │                     │          │
│          ▼                     ▼                     ▼          │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                   SHARED MEMORY BUS                      │  │
│   │   ShortTermMemory  (deque, last 10 cycles per key)       │  │
│   │   LongTermMemory   (JSON, rolling EMA baseline per key)  │  │
│   └──────────────────────────────────────────────────────────┘  │
│                                │                                │
│                                ▼                                │
│                    ┌───────────────────┐                        │
│                    │  RESPONSE AGENT   │                        │
│                    │  alert_system     │◀── feedback loop       │
│                    │  storage          │    (updates LTM)       │
│                    └───────────────────┘                        │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Responsibilities

| Agent | Phase | What it does |
|---|---|---|
| **MonitorAgent** | Observe | Generates logs, extracts features, injects 5 memory-derived fields: velocity, baseline deviation, repeat-offender flag, historical avg, prior observations |
| **DetectionAgent** | Reason | Runs rule engine + IsolationForest in parallel; produces `rule_confidence` and `ml_confidence` per key — not just raw scores |
| **DecisionAgent** | Decide | Confidence-weighted fusion of both engines; selects action via priority ladder; generates full reasoning trace + short summary per verdict |
| **ResponseAgent** | Act | Executes BLOCK / RATE_LIMIT / ALERT / LOG; builds structured alert dicts with reasoning; closes the feedback loop into long-term memory |

---

## Detection Pipeline

1. **Feature Extraction** — Logs grouped by `api_key`. Features: `total_requests`, `average_requests`, `unique_endpoints`, `request_variance` — enriched with memory signals.

2. **Rule Engine** — Heuristic scoring (0–100): high average requests (+40), low endpoint diversity (+30), near-zero variance (+25), extreme behavior bonus (+20).

3. **ML Engine** — IsolationForest scores each key's feature vector for statistical outlier-ness. Scores normalized to 0–100.

4. **Confidence Weighting** — Scores near 50 (ambiguous zone) carry near-zero weight; scores near 0 or 100 carry full weight. Each engine votes proportionally to its certainty.

5. **Fusion** — Confidence-weighted average of both engines. Memory boosts applied: +18 for repeat offenders, +12 for velocity spikes, +10 for >60% baseline deviation.

6. **Decision** — Fused score ≥65 → HIGH, ≥35 → MEDIUM, <35 → LOW. HIGH always BLOCKs. Repeat offenders escalate from MEDIUM to BLOCK automatically.

7. **Feedback** — Every outcome is written into long-term memory (EMA baseline update, HIGH-count increment). The system learns across sessions.

---

## Features

| Feature | Description |
|---|---|
| 4-Type Attack Simulation | Normal · Brute Force · Scraping · DDoS |
| Dual-Engine Detection | IsolationForest (ML) + Rule-based scoring in parallel |
| Confidence-Weighted Fusion | High-confidence engine votes dominate; ambiguous signals abstain |
| Agent Memory | Short-term velocity tracking + long-term behavioral baseline per key |
| Reasoning Traces | Every verdict includes a full explanation of which signals fired |
| Repeat Offender Detection | Keys with 3+ HIGH verdicts auto-escalate on future cycles |
| Action Prioritization | BLOCK > RATE_LIMIT > ALERT > LOG — context-sensitive |
| Live SOC Dashboard | Terminal-noir Streamlit UI with CRT scanlines, phosphor green |
| CLI Agent Runner | `run_agent.py` — run the agent loop in the terminal without the dashboard |

---

## Quick Start

```bash
# 1. Clone & setup
git clone https://github.com/YOUR_USERNAME/ai-redteam.git
cd ai-redteam
python -m venv .venv
.\.venv\Scripts\activate          # Windows
pip install -r requirements.txt

# 2. Launch dashboard
python -m streamlit run src/dashboard.py

# 3. Or run the CLI agent (no dashboard needed)
python run_agent.py                        # normal traffic, infinite loop
python run_agent.py --mode attack          # attack simulation
python run_agent.py --mode suspicious --cycles 10 --interval 2
```

> Dashboard opens at `http://localhost:8501`

---

## Demo Scenarios

Click the buttons in the top bar to switch scenarios instantly:

### 🟢 Normal Traffic
- 85% normal user traffic — low risk scores, green KPIs
- Sample reasoning: `[LOW | conf=78% | fused=11.0] — no significant signals — baseline behavior.`

### 🟡 Suspicious Activity
- 45% attack traffic — MEDIUM scores, amber warnings
- Sample reasoning: `[MEDIUM | conf=30% | fused=48.0] — rule engine: moderately elevated activity (score 55).`

### 🔴 Attack Mode
- 80% attack traffic — HIGH scores spike, keys auto-blocked
- Sample reasoning: `[HIGH | conf=95% | fused=97.6] — rule engine: high-volume/low-diversity (score 95); ML: statistical outlier (anomaly 91.2); short-term memory: velocity spike +70; long-term memory: >=3 prior HIGH verdicts (repeat offender).`

---

## Project Structure

```
ai-redteam/
├── src/
│   ├── agents/
│   │   ├── monitor_agent.py        # Observe: log ingest + memory enrichment
│   │   ├── detection_agent.py      # Reason: rule engine + ML (parallel)
│   │   ├── decision_agent.py       # Decide: confidence fusion + action selection
│   │   └── response_agent.py       # Act: execute + feedback loop
│   │
│   ├── memory/
│   │   ├── short_term.py           # Sliding window per key (velocity, burst detection)
│   │   └── long_term.py            # Persistent EMA baseline per key (JSON)
│   │
│   ├── core/
│   │   ├── agent_loop.py           # Orchestrator: one .run() call per cycle
│   │   ├── confidence.py           # Confidence scoring + weighted fusion
│   │   └── explainer.py            # Reasoning trace + action justification
│   │
│   ├── simulator.py                # Log generator (4 attack types)
│   ├── feature_extractor.py        # Per-key feature engineering
│   ├── risk_engine.py              # Rule-based scoring (0–100)
│   ├── detector.py                 # IsolationForest anomaly detection
│   ├── alert_system.py             # In-memory WAF block list
│   ├── storage.py                  # CSV persistence
│   └── dashboard.py                # Live SOC terminal UI
│
├── data/
│   ├── results.csv                 # Auto-generated each cycle
│   └── memory/
│       └── long_term.json          # Persisted agent memory (gitignored)
│
├── run_agent.py                    # CLI agent runner (no dashboard needed)
├── requirements.txt
└── README.md
```

---

## Tech Stack

- **Python 3.12+**
- **scikit-learn** — IsolationForest anomaly detection
- **pandas / numpy** — feature engineering and data processing
- **Streamlit** — SOC dashboard UI
- **streamlit-autorefresh** — 3-second live pipeline cycle
- **Custom CSS** — terminal-noir aesthetic (VT323 font, CRT scanlines, phosphor green)

---

## Real-World Parallels

This architecture mirrors production security systems:

| VigilAI Component | Production Equivalent |
|---|---|
| MonitorAgent | Log ingestion layer (Splunk forwarder, Kafka consumer) |
| DetectionAgent | SIEM correlation engine (IBM QRadar, Microsoft Sentinel) |
| DecisionAgent | SOAR playbook engine (Palo Alto XSOAR, Splunk SOAR) |
| ResponseAgent | WAF enforcement layer (AWS WAF, Cloudflare) |
| LongTermMemory | Threat intelligence database (MISP, ThreatConnect) |
| Reasoning traces | SOC analyst audit trail |

---

## 🔮 Future Work

VigilAI's modular agent architecture makes the following extensions straightforward:

- **Real API Ingestion** — Replace the simulator with a FastAPI middleware layer that streams live request logs into `MonitorAgent`, enabling deployment against real traffic without changing any downstream agent
- **External Threat Intel** — Integrate feeds from MISP or AbuseIPDB into `LongTermMemory` so the agent can cross-reference IPs and API keys against known threat actor databases
- **LLM-Powered Triage** — Route HIGH-confidence alerts to a Claude/GPT chain that generates a full incident report and suggests remediation steps — closing the loop from detection to operator brief
- **Distributed Multi-Agent Scaling** — Shard `MonitorAgent` across multiple workers (one per API gateway region), with a central `DecisionAgent` aggregating signals — matching how large SIEMs handle multi-region ingestion
- **Adversarial Robustness** — Add evasion-detection logic to flag keys that deliberately keep scores near the 50-point ambiguity boundary (slow-drip attacks designed to stay MEDIUM indefinitely)

---

## Author

**Nikhil** · Cybersecurity & AI Enthusiast

Built VigilAI as a cybersecurity portfolio project demonstrating agentic AI principles applied to real SOC workflows: ML-based anomaly detection, confidence-weighted decision fusion, persistent behavioral memory, and explainable automated response.
