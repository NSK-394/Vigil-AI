# Vigil AI — Autonomous API Abuse Detection

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn-IsolationForest-F7931E?logo=scikitlearn&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-ingest-009688?logo=fastapi&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-SOC_dashboard-FF4B4B?logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-WAL_queue-003B57?logo=sqlite&logoColor=white)
![Product Hunt](https://img.shields.io/badge/Product_Hunt-launched-DA552F?logo=producthunt&logoColor=white)

Vigil detects and responds to API abuse without a human in the loop: four agents
(**Monitor → Detection → Decision → Response**) run a continuous
observe–reason–decide–act cycle that fuses Isolation Forest anomaly scores with a
rule engine, remembers each API key's behavioral baseline across restarts, and
blocks or rate-limits with a full reasoning trace attached to every verdict.
Launched on Product Hunt · [landing page](https://vigil-landing-page.vercel.app)

![Live SOC dashboard](docs/soc-dashboard.png)

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│              AGENT LOOP  (Observe → Reason → Decide → Act)      │
│                                                                 │
│   ┌──────────────┐    ┌─────────────────┐    ┌──────────────┐   │
│   │  MONITOR     │    │  DETECTION      │    │  DECISION    │   │
│   │  log ingest +│───▶│  rule engine ∥  │───▶│  confidence- │   │
│   │  memory      │    │  IsolationForest│    │  weighted    │   │
│   │  enrichment  │    │  (parallel)     │    │  fusion      │   │
│   └──────┬───────┘    └────────┬────────┘    └──────┬───────┘   │
│          ▼                     ▼                    ▼           │
│   ┌──────────────────────────────────────────────────────────┐  │
│   │                   SHARED MEMORY BUS                      │  │
│   │   short-term: deque, last 10 cycles per key (velocity)   │  │
│   │   long-term:  rolling EMA baseline per key (JSON,        │  │
│   │               atomic writes, survives restarts)          │  │
│   └──────────────────────────┬───────────────────────────────┘  │
│                              ▼                                  │
│                   ┌───────────────────┐                         │
│                   │  RESPONSE AGENT   │◀── feedback loop        │
│                   │  BLOCK/RATE_LIMIT │    (updates long-term   │
│                   │  /ALERT/LOG       │     memory each cycle)  │
│                   └───────────────────┘                         │
└─────────────────────────────────────────────────────────────────┘
```

| Agent | Phase | Responsibility |
|---|---|---|
| [MonitorAgent](src/agents/monitor_agent.py) | Observe | Ingests logs, extracts per-key features, injects 5 memory-derived signals (velocity, baseline deviation, repeat-offender flag, historical average, prior observations) |
| [DetectionAgent](src/agents/detection_agent.py) | Reason | Runs the rule engine and Isolation Forest **in parallel**; emits a confidence, not just a score, per engine |
| [DecisionAgent](src/agents/decision_agent.py) | Decide | Confidence-weighted fusion, action selection (BLOCK > RATE_LIMIT > ALERT > LOG), full reasoning trace per verdict |
| [ResponseAgent](src/agents/response_agent.py) | Act | Executes the action, fires Slack/email alerts, writes outcomes back into long-term memory |

## How detection works

1. **Features per API key** — request volume, endpoint diversity, variance — enriched
   with the key's own history from memory.
2. **Two engines in parallel** — a heuristic rule engine (0–100) and an
   [Isolation Forest](src/detector.py) scoring statistical outlier-ness.
3. **Confidence weighting** ([src/core/confidence.py](src/core/confidence.py)) — a
   score near 50 is an engine saying "I don't know", so it carries near-zero weight;
   scores near 0 or 100 carry full weight. Ambiguous engines effectively **abstain**
   instead of dragging the fused score toward the middle.
4. **Memory boosts** — +18 repeat offender (3+ prior HIGH verdicts), +12 velocity
   spike, +10 for >60 % deviation from the key's own EMA baseline.
5. **Decision & feedback** — fused ≥65 → HIGH (always BLOCK), ≥35 → MEDIUM; repeat
   offenders auto-escalate MEDIUM → BLOCK. Every outcome updates the EMA baseline, so
   the system learns across sessions.

Every verdict ships an auditable reasoning trace:

```
[HIGH | conf=95% | fused=97.6] — rule engine: high-volume/low-diversity (score 95);
ML: statistical outlier (anomaly 91.2); short-term memory: velocity spike +70;
long-term memory: >=3 prior HIGH verdicts (repeat offender).
```

## Hardest problems solved

- **Fusing two engines that disagree** — naive averaging lets an uncertain engine
  veto a certain one (rule engine 95, ML 50 → 72.5, under-blocking real attacks).
  The fix is weighting each vote by its *distance from the ambiguity zone*, which
  also creates a known adversarial surface (attackers camping at score ~50) that the
  memory boosts exist to counter.
- **Persistent behavioral memory that can't corrupt** — long-term memory is a per-key
  EMA baseline in JSON, written via temp-file + `os.replace()` so a mid-write crash
  can't corrupt the store ([src/memory/long_term.py](src/memory/long_term.py)).
- **Cross-process ingestion** — real traffic flows middleware → ingest server → agent
  loop through a SQLite WAL queue ([src/live_queue.py](src/live_queue.py)); a race
  between concurrent `push()`/`drain()` and `queue_size()` was found and fixed by
  holding the process lock. The ingest server also caps `request_count` to block
  score-manipulation via forged payloads, and the dashboard HTML-escapes all
  attacker-controlled strings (API keys can carry XSS payloads in real traffic mode).

## Quick start

```bash
git clone https://github.com/NSK-394/Vigil-AI.git && cd Vigil-AI
python -m venv .venv && .venv/Scripts/activate     # source .venv/bin/activate on Unix
pip install -r requirements.txt

python -m streamlit run src/dashboard.py           # SOC dashboard → localhost:8501
python run_agent.py --mode attack --cycles 10      # or headless CLI agent
```

The dashboard simulates four traffic profiles (normal, brute force, scraping, DDoS)
switchable live from the top bar.

## Monitor a real API

Drop-in middleware streams live HTTP traffic into the detection pipeline:

```python
# FastAPI — 2 lines
from src.middleware.fastapi_middleware import VigilMiddleware
app.add_middleware(VigilMiddleware, vigil_url="http://localhost:9000/ingest")
```

```javascript
// Express — built-in modules only, no npm install
const { createVigilMiddleware } = require('./src/middleware/express_middleware');
app.use(createVigilMiddleware({ vigilUrl: 'http://localhost:9000/ingest' }));
```

Run the ingest server (`uvicorn src.middleware.ingest_server:app --port 9000`), and
BLOCK verdicts fire Slack webhook + Gmail alerts in background threads (configure via
`.env`, see [.env.example](.env.example)).

## Production parallels

| Vigil component | Enterprise equivalent |
|---|---|
| DetectionAgent | SIEM correlation engine (QRadar, Sentinel) |
| DecisionAgent | SOAR playbook engine (XSOAR, Splunk SOAR) |
| ResponseAgent | WAF enforcement (AWS WAF, Cloudflare) |
| Long-term memory | Threat-intel database (MISP) |
| Reasoning traces | SOC analyst audit trail |
