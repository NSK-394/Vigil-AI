# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Setup
python -m venv .venv
.venv/Scripts/activate          # Windows
pip install -r requirements.txt

# Run dashboard (Streamlit SOC UI, port 8501)
python -m streamlit run src/dashboard.py

# Run CLI agent loop (no dashboard needed)
python run_agent.py                              # normal traffic, infinite
python run_agent.py --mode attack --cycles 5    # attack preset, 5 cycles
python run_agent.py --mode suspicious --interval 2 --logs 200

# Run API ingestion server (port 8000, captures real HTTP traffic)
python run_server.py

# Run tests (no pytest — each file is a standalone script)
python src/test_integration.py   # master end-to-end test (5 phases)
python src/test_agents.py
python src/test_core.py
python src/test_memory.py
python src/test_risk.py
python src/test_features.py
python src/test_alerts.py
python src/test_simulator.py
```

All test scripts must be run from the **project root** (not from `src/`).

## Architecture

### Agent Loop
The canonical entry point is `AgentLoop` in `src/core/agent_loop.py`. One `.run()` call executes a full **Observe → Reason → Decide → Act** cycle:

```
MonitorAgent.observe()          # ingest logs + extract features + memory enrichment
  → DetectionAgent.analyze()    # rule engine (risk_engine.py) + ML (detector.py) in parallel
  → DecisionAgent.decide()      # confidence-weighted fusion + action selection + reasoning trace
  → ResponseAgent.act()         # execute actions + update long-term memory + persist CSV
```

### Two Data Sources
`MonitorAgent.observe(source=...)` supports:
- `"simulated"` (default) — generates synthetic logs via `simulator.py`
- `"real"` — drains the SQLite queue written by `api_server.py` (live HTTP traffic)

The dashboard and `run_agent.py` use simulated mode. The `api_server.py` (port 8000) uses real mode — it captures every inbound request into `data/live_queue.db`.

### Cross-Process Queue
The dashboard and API server run as separate OS processes. They share state only through `live_queue.py`, a SQLite WAL-mode queue at `data/live_queue.db`. `push(log)` is called by the API server middleware; `drain(n)` is called by MonitorAgent. There is no in-memory shared state between processes.

### Feature Pipeline
Raw logs are grouped by `api_key` by `feature_extractor.py`. Each log's `request_count` field (NOT 1-per-request in simulator mode — it's an aggregated window count) determines:
- `total_requests = sum(request_count)`
- `average_requests = mean(request_count)` ← primary risk signal
- `unique_endpoints` ← endpoint diversity signal
- `request_variance` ← uniformity signal

These 4 features feed both the rule engine and IsolationForest. IsolationForest is retrained from scratch every cycle (no persistence) and requires ≥2 feature rows; with only 1 row it falls back to a neutral score of 50.

### Scoring & Decision Logic
- **Rule engine** (`risk_engine.py`): scores 0–100 from the 4 features; labels LOW/MEDIUM/HIGH
- **ML engine** (`detector.py`): IsolationForest anomaly score normalized to 0–100
- **Confidence** (`core/confidence.py`): scores near 50 (ambiguous) carry near-zero weight; scores near 0 or 100 carry full weight
- **Fusion** (`core/confidence.py:weighted_fusion`): confidence-weighted blend; memory boosts applied after (+18 repeat offender, +12 velocity spike, +10 >60% baseline deviation)
- **Thresholds**: fused ≥65 → HIGH, ≥35 → MEDIUM, <35 → LOW
- **Action ladder**: HIGH→BLOCK; MEDIUM+repeat_offender→BLOCK; MEDIUM→RATE_LIMIT; anomaly or velocity spike→ALERT; else LOG

### Memory System
- **ShortTermMemory** (`src/memory/short_term.py`): per-process deque, last 10 observations per key; used for velocity (delta from previous window)
- **LongTermMemory** (`src/memory/long_term.py`): JSON file at `data/memory/long_term.json` (gitignored); survives restarts; EMA baseline per key + HIGH count for repeat-offender detection (threshold: 3 HIGHs)

### sys.path Convention
All modules inside `src/` import each other with **bare names** (`from risk_engine import ...`, not `from src.risk_engine import ...`). This works because every entry point (`run_agent.py`, `run_server.py`, `dashboard.py`, test scripts) inserts `src/` onto `sys.path` at startup. Never add a `src.` prefix to intra-package imports.

### Legacy vs Agentic Pipeline
There is a legacy pipeline (`decision_engine.py`, `actions.py`, `final_decision.py`, `finaltest.py`, `teststorange.py`) that predates the 4-agent architecture. It is no longer the active code path. The agentic path through `core/agent_loop.py` is authoritative.

### Alert System
`alert_system.py` holds the in-memory WAF block list (`blocked_keys: set`) shared by the entire process. `ResponseAgent` calls `block_api_key()` directly. The `generate_alerts()` function is legacy; the agentic path uses `ResponseAgent._build_alert()` instead.
