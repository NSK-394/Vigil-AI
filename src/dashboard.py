"""
dashboard.py  ·  VigilAI
────────────────────────────────────
Aesthetic: Pure retro-terminal SOC warroom.
  - Phosphor green on true black
  - CRT scanlines + screen flicker
  - Monospace everything
  - Live scrolling terminal log via st.empty()
  - No normal Streamlit charts — raw ASCII and HTML tables only

Run:
    streamlit run dashboard.py

Data:  data/results.csv  (from final_decision.py)
       data/logs.csv     (from simulator.py)
If files are missing → auto-generates demo data.
"""

import sys
import os
import random
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

# ── Make sure src/ modules are importable when running from project root ──
_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from core.agent_loop import AgentLoop
from alert_system    import get_blocked_keys


# ──────────────────────────────────────────────────────────────
#  PAGE CONFIG  (must be the very first Streamlit call)
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VigilAI",
    page_icon="💀",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# Autorefresh every 3 s — each rerun = one full pipeline cycle
st_autorefresh(interval=3000, key="live_pipeline")


# ──────────────────────────────────────────────────────────────
#  GLOBAL CSS  ·  everything that makes it look like a terminal
# ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=VT323&family=Share+Tech+Mono&display=swap');

/* ── CSS variables ── */
:root {
    --green:      #00ff41;
    --green-dim:  #00aa2a;
    --green-dark: #003b0f;
    --amber:      #ffb000;
    --red:        #ff2222;
    --cyan:       #00ffff;
    --bg:         #000000;
    --bg2:        #020f05;
    --border:     #00ff4122;
}

/* ── Wipe out all Streamlit chrome ── */
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"]          { display: none !important; }
[data-testid="stSidebar"]               { display: none !important; }
section[data-testid="stSidebar"]        { display: none !important; }

/* ── Base page ── */
html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"], .main          {
    background: var(--bg) !important;
    color: var(--green) !important;
    font-family: 'Share Tech Mono', monospace !important;
}
.block-container {
    padding: 0.8rem 1.4rem 2rem !important;
    max-width: 100% !important;
}

/* ── CRT phosphor scanlines ── */
[data-testid="stAppViewContainer"]::before {
    content: "";
    position: fixed; top: 0; left: 0;
    width: 100vw; height: 100vh;
    background: repeating-linear-gradient(
        0deg,
        transparent 0px,
        transparent 1px,
        rgba(0,255,65,0.025) 1px,
        rgba(0,255,65,0.025) 2px
    );
    pointer-events: none;
    z-index: 9998;
}

/* ── CRT flicker on whole page ── */
@keyframes crt-flicker {
    0%, 97%, 100% { opacity: 1; }
    98%            { opacity: 0.92; }
    99%            { opacity: 1; }
    99.5%          { opacity: 0.88; }
}
[data-testid="stAppViewContainer"] {
    animation: crt-flicker 8s infinite;
}

/* ══════════════════════════════════════════════
   TOP BAR — the terminal title strip
══════════════════════════════════════════════ */

@keyframes neon-flicker {
    0%,18%,20%,52%,54%,100% {
        text-shadow: 0 0 4px var(--green), 0 0 14px var(--green), 0 0 32px #00ff4188;
    }
    19%, 53% { text-shadow: none; opacity: 0.85; }
}
.term-title {
    font-family: 'VT323', monospace;
    font-size: 2.6rem;
    color: var(--green);
    letter-spacing: 0.1em;
    line-height: 1;
    animation: neon-flicker 5s infinite;
}

/* Blinking block cursor */
@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }
.cursor {
    display: inline-block;
    width: 18px; height: 2.2rem;
    background: var(--green);
    vertical-align: middle;
    margin-left: 6px;
    animation: blink 1.1s step-end infinite;
}
.term-meta {
    font-size: 0.68rem;
    color: var(--green-dim);
    letter-spacing: 0.2em;
    line-height: 1.8;
}

/* ── Status bar top-right ── */
.status-bar {
    text-align: right;
    font-size: 0.72rem;
    color: var(--green-dim);
    letter-spacing: 0.15em;
    line-height: 2;
}
.status-online { color: var(--green); text-shadow: 0 0 8px var(--green); }

/* ── Alert banner ── */
@keyframes alert-pulse {
    0%,100% { background:#1a000088; border-color: var(--red); color: var(--red); }
    50%      { background:#3a000099; border-color: #ff8888;   color: #ff8888;    }
}
.alert-banner {
    border: 1px solid var(--red);
    border-radius: 2px;
    padding: 7px 16px;
    font-size: 0.78rem;
    letter-spacing: 0.25em;
    text-transform: uppercase;
    animation: alert-pulse 1.4s ease-in-out infinite;
    text-align: center;
    margin-bottom: 8px;
}

/* ── Animated glow on alert (incident) cards ── */
@keyframes alert-card-glow {
    0%,100% { box-shadow: 0 0 4px #ff222233; border-left-color: #ff2222; }
    50%      { box-shadow: 0 0 18px #ff222288; border-left-color: #ff6666; }
}
.alert-card-live {
    animation: alert-card-glow 1.2s ease-in-out infinite;
}

/* ── Section headers look like terminal prompts ── */
.term-header {
    font-family: 'Share Tech Mono', monospace;
    font-size: 0.72rem;
    color: var(--green-dim);
    letter-spacing: 0.3em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    padding-bottom: 5px;
    margin: 14px 0 10px;
}
.term-header::before { content: "root@threat-engine:~$ "; color: var(--green); }

/* ── Terminal log box ── */
.log-box {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 2px;
    padding: 10px 14px;
    height: 340px;
    overflow-y: auto;
    font-size: 0.72rem;
    line-height: 1.9;
    font-family: 'Share Tech Mono', monospace;
}
.log-box::-webkit-scrollbar       { width: 4px; }
.log-box::-webkit-scrollbar-track { background: #000; }
.log-box::-webkit-scrollbar-thumb { background: var(--green-dark); border-radius: 2px; }

.log-ok     { color: var(--green-dim); }
.log-warn   { color: var(--amber); }
.log-alert  { color: var(--red); font-weight: bold; letter-spacing:.05em; }
.log-info   { color: var(--cyan); }
.log-system { color: #555; font-style: italic; }
.log-ts     { color: #00ff4155; margin-right: 8px; }

/* ── KPI strip ── */
.kpi-strip {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-left: 3px solid;
    border-radius: 2px;
    padding: 12px 16px;
    text-align: center;
}
.kpi-val {
    font-family: 'VT323', monospace;
    font-size: 2.8rem;
    line-height: 1;
}
.kpi-lbl {
    font-size: 0.6rem;
    color: var(--green-dim);
    letter-spacing: 0.25em;
    text-transform: uppercase;
    margin-top: 2px;
}

/* ── Threat table ── */
.term-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.72rem;
    font-family: 'Share Tech Mono', monospace;
}
.term-table th {
    color: var(--green-dim);
    border-bottom: 1px solid var(--border);
    padding: 6px 10px;
    text-align: left;
    letter-spacing: .2em;
    font-weight: normal;
    font-size: 0.65rem;
    text-transform: uppercase;
}
.term-table td {
    padding: 7px 10px;
    border-bottom: 1px solid #00ff410a;
    color: #ffffffaa;
    vertical-align: middle;
}
.term-table tr:hover td { background: #00ff410a; }

.pill         { display:inline-block; padding:1px 9px; border-radius:2px; font-size:0.68rem; letter-spacing:.12em; font-weight:bold; }
.pill-HIGH    { color: var(--red);   border:1px solid var(--red);   background:#ff000015; }
.pill-MEDIUM  { color: var(--amber); border:1px solid var(--amber); background:#ff990015; }
.pill-LOW     { color: var(--green); border:1px solid var(--green-dark); background:#00ff410d; }

/* ── ASCII bar ── */
.ascii-bar-wrap { display:flex; align-items:center; gap:8px; font-family:'Share Tech Mono',monospace; font-size:0.68rem; }
.ascii-bar { letter-spacing:-1px; }

/* ── AI insight panel ── */
.insight-panel {
    background: #001a06;
    border: 1px solid #00ff4133;
    border-left: 3px solid var(--green);
    border-radius: 2px;
    padding: 14px 18px;
    font-size: 0.72rem;
    color: #ffffffaa;
    line-height: 1.9;
    position: relative;
    overflow: hidden;
}
@keyframes shimmer { from{left:-100%} to{left:100%} }
.insight-panel::before {
    content: "";
    position: absolute; top: 0; left: -100%;
    width: 60%; height: 1px;
    background: linear-gradient(90deg, transparent, var(--green), transparent);
    animation: shimmer 3s linear infinite;
}
.insight-hdr {
    font-size: 0.65rem;
    color: var(--green);
    letter-spacing: .3em;
    text-transform: uppercase;
    margin-bottom: 8px;
}
.hl  { color: var(--green);  font-weight: bold; }
.wrn { color: var(--amber); }
.err { color: var(--red);   font-weight: bold; }
.cod { background:#ffffff0d; border:1px solid #ffffff1a; padding:0 5px; border-radius:2px; color:var(--green); font-size:0.68rem; }

/* ── HR ── */
.term-hr { border:none; border-top:1px solid var(--border); margin:14px 0; }

/* ── Selectbox label ── */
label[data-testid="stWidgetLabel"] p {
    color: var(--green-dim) !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.68rem !important;
    letter-spacing: .2em !important;
    text-transform: uppercase !important;
}

/* ── Scenario status badge ── */
.status-badge {
    display: inline-block;
    font-family: 'VT323', monospace;
    font-size: 1.15rem;
    letter-spacing: .1em;
    padding: 5px 14px;
    border-radius: 3px;
    border: 2px solid;
    text-align: center;
    white-space: nowrap;
    width: 100%;
    box-sizing: border-box;
}
.status-normal     { color: #00ff41; border-color: #00ff41; background: #00ff4110;
                     text-shadow: 0 0 12px #00ff41; box-shadow: 0 0 10px #00ff4122; }
.status-suspicious { color: #ffb000; border-color: #ffb000; background: #ffb00010;
                     text-shadow: 0 0 12px #ffb000; box-shadow: 0 0 10px #ffb00022;
                     animation: alert-pulse 2s infinite; }
.status-attack     { color: #ff2222; border-color: #ff2222; background: #ff222215;
                     text-shadow: 0 0 12px #ff2222; box-shadow: 0 0 14px #ff222244;
                     animation: alert-pulse 0.6s infinite; }

/* ── Sim button ── */
[data-testid="stButton"] > button {
    background: #0a1a0a !important;
    color: #00ff41 !important;
    border: 1px solid #00ff4166 !important;
    font-family: 'Share Tech Mono', monospace !important;
    font-size: 0.72rem !important;
    letter-spacing: .15em !important;
    border-radius: 2px !important;
    transition: all 0.2s !important;
}
[data-testid="stButton"] > button:hover {
    background: #001a00 !important;
    border-color: #00ff41 !important;
    box-shadow: 0 0 14px #00ff4155 !important;
}
.attack-btn [data-testid="stButton"] > button {
    color: #ff2222 !important;
    border-color: #ff222299 !important;
    animation: alert-pulse 1s infinite;
}
/* Force all 3 scenario buttons to equal height and baseline */
[data-testid="stHorizontalBlock"] [data-testid="stButton"] > button {
    height: 38px !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    width: 100% !important;
}
/* Tighten the gap between the 3 scenario buttons */
[data-testid="stHorizontalBlock"] {
    gap: 6px !important;
}
</style>
""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  COLOUR HELPER
# ──────────────────────────────────────────────────────────────

def get_color(label: str) -> str:
    """Map a threat label to its terminal neon colour."""
    return {"HIGH": "#ff2222", "MEDIUM": "#ffb000", "LOW": "#00ff41"}.get(
        str(label).upper(), "#ffffff"
    )


# ──────────────────────────────────────────────────────────────
#  DEMO DATA GENERATORS
# ──────────────────────────────────────────────────────────────

ENDPOINTS = ["/api/login", "/api/search", "/api/products",
             "/api/checkout", "/api/user/profile", "/api/logout"]

def _demo_logs(n: int = 80) -> pd.DataFrame:
    now, rows = datetime.now(), []
    attack_types = ["normal", "brute_force", "scraping", "ddos"]
    weights      = [0.60, 0.15, 0.15, 0.10]
    for _ in range(n):
        atype = random.choices(attack_types, weights=weights, k=1)[0]
        if atype == "normal":
            rows.append({
                "api_key": f"user_key_{random.randint(1,40):03d}",
                "endpoint": random.choice(ENDPOINTS), "request_count": random.randint(1, 15),
                "timestamp": (now - timedelta(seconds=random.randint(0, 3600))).strftime("%Y-%m-%d %H:%M:%S"),
                "ip_address": f"192.168.{random.randint(0,10)}.{random.randint(1,254)}",
                "attack_type": "normal",
            })
        elif atype == "brute_force":
            rows.append({
                "api_key": f"brute_key_{random.randint(1,5):03d}",
                "endpoint": "/api/login", "request_count": random.randint(200, 800),
                "timestamp": (now - timedelta(seconds=random.randint(0, 300))).strftime("%Y-%m-%d %H:%M:%S"),
                "ip_address": f"91.121.{random.randint(1,254)}.{random.randint(1,254)}",
                "attack_type": "brute_force",
            })
        elif atype == "scraping":
            rows.append({
                "api_key": f"scrape_key_{random.randint(1,5):03d}",
                "endpoint": random.choice(ENDPOINTS), "request_count": random.randint(50, 300),
                "timestamp": (now - timedelta(seconds=random.randint(0, 1200))).strftime("%Y-%m-%d %H:%M:%S"),
                "ip_address": f"104.21.{random.randint(1,254)}.{random.randint(1,254)}",
                "attack_type": "scraping",
            })
        else:  # ddos
            rows.append({
                "api_key": f"ddos_key_{random.randint(1,3):03d}",
                "endpoint": random.choice(ENDPOINTS[:2]), "request_count": random.randint(1000, 5000),
                "timestamp": (now - timedelta(seconds=random.randint(0, 30))).strftime("%Y-%m-%d %H:%M:%S"),
                "ip_address": f"5.188.{random.randint(1,254)}.{random.randint(1,254)}",
                "attack_type": "ddos",
            })
    return pd.DataFrame(rows)

def _demo_results(n: int = 35) -> pd.DataFrame:
    rows = []
    for i in range(1, 6):
        rows.append({"api_key": f"bot_key_{i:03d}",  "risk_score": random.randint(72,98),  "anomaly_score": round(random.uniform(80,99),1),  "final_label": "HIGH"})
    for i in range(1, 9):
        rows.append({"api_key": f"user_key_{i:03d}", "risk_score": random.randint(32,69),  "anomaly_score": round(random.uniform(30,65),1),  "final_label": "MEDIUM"})
    for i in range(9, max(10, n - 12)):
        rows.append({"api_key": f"user_key_{i:03d}", "risk_score": random.randint(0,28),   "anomaly_score": round(random.uniform(0,25),1),   "final_label": "LOW"})
    return pd.DataFrame(rows)


# ──────────────────────────────────────────────────────────────
#  SIMULATION MODE  —  session_state controls traffic mix
# ──────────────────────────────────────────────────────────────

# Initialise state
if "sim_mode" not in st.session_state:
    st.session_state["sim_mode"] = "normal"        # normal | suspicious | attack
if "attack_cycles" not in st.session_state:
    st.session_state["attack_cycles"] = 0

# AgentLoop persists across reruns so LTM survives each 3-second refresh cycle
if "agent_loop" not in st.session_state:
    os.makedirs("data/memory", exist_ok=True)
    st.session_state["agent_loop"] = AgentLoop(
        ltm_path="data/memory/long_term.json",
        results_path="data/results.csv",
    )
loop: AgentLoop = st.session_state["agent_loop"]

# Traffic-mix presets per demo scenario
TRAFFIC_PRESETS = {
    "normal":     {"normal": 0.85, "brute_force": 0.05, "scraping": 0.07, "ddos": 0.03},
    "suspicious": {"normal": 0.55, "brute_force": 0.20, "scraping": 0.18, "ddos": 0.07},
    "attack":     {"normal": 0.20, "brute_force": 0.35, "scraping": 0.25, "ddos": 0.20},
}

# After an attack is triggered, run 4 attack cycles then cool down
if st.session_state["attack_cycles"] > 0:
    st.session_state["sim_mode"]      = "attack"
    st.session_state["attack_cycles"] -= 1
elif st.session_state["attack_cycles"] == 0 and st.session_state["sim_mode"] == "attack":
    st.session_state["sim_mode"] = "normal"

current_mode = st.session_state["sim_mode"]
current_mix  = TRAFFIC_PRESETS[current_mode]

# ──────────────────────────────────────────────────────────────
#  AGENT LOOP  —  one full Observe→Reason→Decide→Act cycle
# ──────────────────────────────────────────────────────────────

os.makedirs("data", exist_ok=True)
try:
    _result          = loop.run(n_logs=100, traffic_mix=current_mix)
    logs_df          = pd.DataFrame(_result["logs"])
    results_df       = pd.DataFrame(_result["decisions"])
    decisions        = _result["decisions"]
    alerts_this_cycle    = _result["alerts"]
    loop_stats           = _result["stats"]
    blocked_this_session = loop.blocked_keys()
except Exception as e:
    st.sidebar.error(f"Agent loop error: {e}")
    logs_df              = _demo_logs(80)
    results_df           = _demo_results(35)
    decisions            = []
    alerts_this_cycle    = []
    loop_stats           = {}
    blocked_this_session = []

high_count   = int((results_df["final_label"] == "HIGH").sum())  if not results_df.empty else 0
medium_count = int((results_df["final_label"] == "MEDIUM").sum()) if not results_df.empty else 0
low_count    = int((results_df["final_label"] == "LOW").sum())    if not results_df.empty else 0
total_keys   = len(results_df)
total_reqs   = int(logs_df["request_count"].sum()) if "request_count" in logs_df.columns else 0
avg_conf     = loop_stats.get("avg_confidence", 0.0)
avg_conf_pct = f"{avg_conf:.0%}"

# new-threat flash: compare to previous tick stored in session_state
prev_high = st.session_state.get("prev_high", high_count)
new_threats_detected = high_count > prev_high
st.session_state["prev_high"] = high_count

label_order    = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
sorted_results = results_df.copy()
sorted_results["_ord"] = sorted_results["final_label"].map(label_order)
sorted_results = sorted_results.sort_values(["_ord","risk_score"],ascending=[True,False]).drop(columns="_ord")


# ──────────────────────────────────────────────────────────────
#  ASCII BAR HELPER
# ──────────────────────────────────────────────────────────────

def ascii_bar(value: float, width: int = 20, color: str = "#00ff41") -> str:
    """Return HTML ASCII progress bar for a 0-100 score."""
    filled = int((value / 100) * width)
    empty  = width - filled
    bar    = "█" * filled + "░" * empty
    return (
        f'<span class="ascii-bar" style="color:{color}">[{bar}]</span>'
        f'<span style="color:{color}88; font-size:0.65rem"> {int(value)}</span>'
    )


# ──────────────────────────────────────────────────────────────
#  AI INSIGHT ENGINE
# ──────────────────────────────────────────────────────────────

def generate_ai_insight(row: pd.Series, logs_df: pd.DataFrame) -> str:
    """Build context-aware insight HTML for one api_key."""
    label   = str(row.get("final_label", "LOW")).upper()
    risk    = float(row.get("risk_score",    0))
    anomaly = float(row.get("anomaly_score", 0))
    api_key = str(row.get("api_key", "unknown"))

    key_logs = logs_df[logs_df["api_key"] == api_key] if "api_key" in logs_df.columns else pd.DataFrame()
    if not key_logs.empty and "endpoint" in key_logs.columns:
        top_ep   = key_logs["endpoint"].value_counts().idxmax()
        ep_hits  = int(key_logs["endpoint"].value_counts().max())
        uniq_eps = int(key_logs["endpoint"].nunique())
        total_r  = int(key_logs["request_count"].sum()) if "request_count" in key_logs.columns else "?"
    else:
        top_ep, ep_hits, uniq_eps, total_r = "/api/login", "N/A", 1, "N/A"

    if label == "HIGH":
        driver = "ML anomaly model" if anomaly >= risk else "rule-based engine"
        score  = anomaly if anomaly >= risk else risk
        return (
            f'<span class="err">[ HIGH THREAT CONFIRMED ]</span><br>'
            f'Primary detection engine: <span class="hl">{driver}</span> '
            f'· score <span class="err">{score}/100</span><br>'
            f'Endpoint concentration: <span class="wrn">{ep_hits}×</span> hits on '
            f'<span class="cod">{top_ep}</span> out of only '
            f'<span class="wrn">{uniq_eps}</span> unique route(s)<br>'
            f'Total requests logged: <span class="err">{total_r}</span><br>'
            f'Pattern match: <span class="err">credential stuffing</span> / '
            f'<span class="err">automated scraping</span><br>'
            f'<span class="wrn">→ ACTION:</span> rate-limit + CAPTCHA + escalate to SOC L2'
        )
    elif label == "MEDIUM":
        return (
            f'<span class="wrn">[ BORDERLINE BEHAVIOUR — MONITORING ]</span><br>'
            f'Rule score: <span class="wrn">{int(risk)}/100</span> · '
            f'ML score: <span class="wrn">{anomaly}/100</span><br>'
            f'Traffic concentrated on <span class="cod">{top_ep}</span> '
            f'({ep_hits}× hits) — possible <span class="hl">power user</span> '
            f'or early-stage probe<br>'
            f'Unique endpoints accessed: <span class="hl">{uniq_eps}</span><br>'
            f'<span class="wrn">→ ACTION:</span> monitor next 15 min · set auto-escalation threshold'
        )
    else:
        return (
            f'<span class="hl">[ NO THREAT DETECTED ]</span><br>'
            f'Risk: <span class="hl">{int(risk)}/100</span> · '
            f'Anomaly: <span class="hl">{anomaly}/100</span><br>'
            f'Accessed <span class="hl">{uniq_eps}</span> distinct endpoint(s) '
            f'with natural variance<br>'
            f'Behaviour consistent with <span class="hl">genuine human browsing</span><br>'
            f'<span class="hl">→ ACTION:</span> no action required · continue passive monitoring'
        )


# ──────────────────────────────────────────────────────────────
#  TERMINAL LOG MESSAGES POOL
# ──────────────────────────────────────────────────────────────

# (css_class, message_template)  —  {key} {ep} {ip} {req} are filled at runtime
LOG_POOL = [
    ("log-system",  "kernel: netfilter hook registered on eth0"),
    ("log-system",  "syslog: inotify watch active on /var/log/api/"),
    ("log-system",  "HEALTH  ↻ watchdog ping OK  [uptime: stable]"),
    ("log-system",  "GC      ↻ log buffer rotated · 1024 entries flushed"),
    ("log-info",    "INGEST  ← {req} packets received from {ip}"),
    ("log-info",    "PARSE   ← api_key={key}  endpoint={ep}  count={req}"),
    ("log-info",    "MODEL   ← IsolationForest re-scored {key}"),
    ("log-info",    "ENGINE  ← rule pipeline processed {req} events"),
    ("log-ok",      "NORM    ✓ {key} — request volume within threshold"),
    ("log-ok",      "PASS    ✓ {key} — endpoint diversity OK ({ep})"),
    ("log-ok",      "CLEAR   ✓ {key} — both engines report LOW risk"),
    ("log-warn",    "WATCH   ⚑ {key} — elevated request rate detected"),
    ("log-warn",    "SCAN    ⚑ {key} — repeated access to {ep} flagged"),
    ("log-warn",    "PROTO   ⚑ unusual User-Agent pattern from {ip}"),
    ("log-alert",   "THREAT  ✖ {key} — anomaly score CRITICAL"),
    ("log-alert",   "BLOCK   ✖ rate-limiting applied → {ip}"),
    ("log-alert",   "ALERT   ✖ bot signature matched on {key}"),
    ("log-alert",   "DETECT  ✖ {key} hammering {ep} · {req} hits/min"),
]

def _random_log_line(logs_df: pd.DataFrame) -> tuple[str, str]:
    """Pick a random log template and substitute real data."""
    cls, tpl = random.choice(LOG_POOL)
    if not logs_df.empty:
        row = logs_df.sample(1).iloc[0]
        key = str(row.get("api_key",       "user_key_??"))
        ep  = str(row.get("endpoint",      "/api/??"))
        ip  = str(row.get("ip_address",    "0.0.0.0"))
        req = str(row.get("request_count", "?"))
    else:
        key, ep, ip, req = "user_key_042", "/api/login", "192.168.1.1", "7"
    return cls, tpl.format(key=key, ep=ep, ip=ip, req=req)

def _render_log_lines(lines: list[tuple[str, str]]) -> str:
    """Convert list of (css_class, message) → HTML for the log box."""
    ts_now = datetime.now()
    html   = ""
    for i, (cls, msg) in enumerate(lines):
        ts_str = (ts_now - timedelta(seconds=len(lines) - i)).strftime("%H:%M:%S")
        html  += f'<div class="{cls}"><span class="log-ts">[{ts_str}]</span>{msg}</div>'
    html += '<div id="log-bottom"></div>'
    return html


# ──────────────────────────────────────────────────────────────
#  ▓▓  TOP BAR
# ──────────────────────────────────────────────────────────────

top_left, top_mid, top_ctrl, top_right = st.columns([2.6, 1.9, 2.4, 1.1])
now   = datetime.now()
cycle = st.session_state.get("cycle", 0) + 1
st.session_state["cycle"] = cycle

# Map mode to badge metadata
_BADGE = {
    "normal":     ("status-normal",     "🟢 NORMAL"),
    "suspicious": ("status-suspicious", "🟡 SUSPICIOUS"),
    "attack":     ("status-attack",     "🔴 UNDER ATTACK"),
}
_badge_cls, _badge_txt = _BADGE[current_mode]

with top_left:
    st.markdown(f"""
    <div class="term-title">💀 VigilAI<span class="cursor"></span></div>
    <div class="term-meta" style="color:#00ff4188; letter-spacing:.18em; font-size:0.65rem; margin-top:4px">
        Real-Time API Threat Intelligence &amp; Anomaly Detection
    </div>
    <div class="term-meta">
        root@soc-engine &nbsp;·&nbsp; {now.strftime("%A %Y-%m-%d")}
        &nbsp;·&nbsp; PID 31337 &nbsp;·&nbsp; SESSION ACTIVE
        &nbsp;·&nbsp; <span style="color:#00ff41">CYCLE #{cycle}</span>
    </div>""", unsafe_allow_html=True)

with top_mid:
    st.markdown(f"""
    <div style="padding-top:14px; text-align:center">
        <div class="status-badge {_badge_cls}">{_badge_txt}</div>
        <div style="font-size:0.58rem; color:#ffffff33; letter-spacing:.2em; margin-top:4px">
            SYSTEM STATUS</div>
    </div>""", unsafe_allow_html=True)

with top_ctrl:
    st.markdown('<div style="padding-top:10px">', unsafe_allow_html=True)
    ctrl_label = st.markdown(
        '<div style="font-size:0.6rem; color:#00ff4166; letter-spacing:.25em; margin-bottom:4px">▶ DEMO SCENARIO</div>',
        unsafe_allow_html=True)
    b1, b2, b3 = st.columns([1, 1, 1], gap="small")
    with b1:
        if st.button("🟢 NORMAL"):
            st.session_state["sim_mode"]      = "normal"
            st.session_state["attack_cycles"] = 0
    with b2:
        if st.button("🟡 SUS"):
            st.session_state["sim_mode"]      = "suspicious"
            st.session_state["attack_cycles"] = 0
    with b3:
        if st.button("🔴 ATTACK!"):
            st.session_state["sim_mode"]      = "attack"
            st.session_state["attack_cycles"] = 8
    st.markdown('</div>', unsafe_allow_html=True)

with top_right:
    st.markdown(f"""
    <div class="status-bar">
        <span style="font-family:'VT323',monospace; font-size:1.1rem; color:#00ff41;
            text-shadow:0 0 10px #00ff41; letter-spacing:.12em">VigilAI</span>
        <span style="color:#00ff4166; font-size:0.65rem"> v1.0</span><br>
        STATUS: <span class="status-online">ONLINE</span> | LATENCY: {random.randint(12, 35)}ms<br>
        LAST SCAN: {now.strftime("%H:%M:%S")} UTC<br>
        MONITORING: {total_keys} keys &nbsp;·&nbsp; ↻ 3s
    </div>""", unsafe_allow_html=True)

# new-threat detected flash (appears for 1 render cycle only)
if new_threats_detected:
    st.markdown(
        f'<div class="alert-banner" style="background:#4d0000; color:#ff4444; '
        f'font-size:1rem; border:2px solid #ff4444;">'
        f'🚨 NEW THREAT ESCALATED — high-risk count rose to {high_count} this cycle 🚨</div>',
        unsafe_allow_html=True,
    )

if high_count > 0:
    st.markdown(
        f'<div class="alert-banner" style="background:#ff0000; color:#ffffff; font-weight:bold; font-size:1.4rem; border:2px solid white; animation: alert-pulse 0.5s infinite alternate;">'
        f'🚨 CRITICAL ALERT: {high_count} HIGH-RISK KEY{"S" if high_count > 1 else ""} DETECTED 🚨</div>',
        unsafe_allow_html=True,
    )
    st.warning("🚨 Threat detected!")

st.markdown('<hr class="term-hr">', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  ▓▓  KPI STRIP
# ──────────────────────────────────────────────────────────────

st.markdown('<div class="term-header">system status</div>', unsafe_allow_html=True)

k1, k2, k3, k4, k5, k6 = st.columns(6)
kpis = [
    (k1, str(total_keys),   "KEYS MONITORED", "#00ff41", "#00ff41"),
    (k2, str(high_count),   "HIGH THREATS",   "#ff2222", "#ff2222"),
    (k3, str(medium_count), "MEDIUM",         "#ffb000", "#ffb000"),
    (k4, str(low_count),    "CLEAR",          "#00ff41", "#00aa2a"),
    (k5, f"{total_reqs:,}", "TOTAL REQUESTS", "#00ffff", "#00ffff"),
    (k6, avg_conf_pct,      "AVG CONFIDENCE", "#aa66ff", "#aa66ff"),
]
for col, val, lbl, val_color, border_color in kpis:
    with col:
        st.markdown(f"""
        <div class="kpi-strip" style="border-left-color:{border_color}">
            <div class="kpi-val" style="color:{val_color};
                 text-shadow:0 0 12px {val_color}88">{val}</div>
            <div class="kpi-lbl">{lbl}</div>
        </div>""", unsafe_allow_html=True)

st.markdown('<hr class="term-hr">', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  ▓▓  2-COLUMN BODY: live terminal feed | threat table
# ──────────────────────────────────────────────────────────────

col_term, col_threats = st.columns([1, 1], gap="large")


# ── LEFT: LIVE SCROLLING TERMINAL  (st.empty() trick) ────────
with col_term:
    st.markdown('<div class="term-header">live terminal output</div>', unsafe_allow_html=True)

    # Seed with boot messages + real log rows
    seed_lines: list[tuple[str, str]] = [
        ("log-system", "kernel: system boot sequence complete"),
        ("log-system", "syslog: loading threat detection modules..."),
        ("log-info",   f"INIT    ← {total_keys} API keys loaded into watchlist"),
        ("log-info",   f"MODEL   ← IsolationForest trained on {len(logs_df)} log entries"),
        ("log-info",   f"RULES   ← {len(results_df)} keys scored by rule engine"),
    ]

    feed_df = logs_df.copy()
    if "timestamp" in feed_df.columns:
        feed_df = feed_df.sort_values("timestamp").tail(16)
    else:
        feed_df = feed_df.tail(16)

    for _, row in feed_df.iterrows():
        atype = str(row.get("attack_type", row.get("label", "normal"))).lower()
        key = str(row.get("api_key",       ""))
        ep  = str(row.get("endpoint",      ""))
        req = str(row.get("request_count", ""))
        ip  = str(row.get("ip_address",    ""))
        ts  = str(row.get("timestamp",     ""))[-8:]
        if atype == "ddos":
            seed_lines.append(("log-alert", f"DDOS    ✗ [{ts}] {key} → {ep} · {req} reqs · {ip}"))
        elif atype == "brute_force":
            seed_lines.append(("log-alert", f"BRUTE   ✗ [{ts}] {key} → {ep} · {req} attempts"))
        elif atype == "scraping":
            seed_lines.append(("log-warn",  f"SCRAPE  ⛑ [{ts}] {key} → {ep} · {req} reqs"))
        else:
            seed_lines.append(("log-ok",    f"PASS    ✓ [{ts}] {key} → {ep} · {req} reqs"))

    if high_count > 0:
        seed_lines.append(("log-alert", f"SUMMARY ✖ {high_count} HIGH-RISK keys confirmed"))
    if "term_logs" not in st.session_state:
        seed_lines.append(("log-system", "watchdog: entering continuous scan loop..."))
        st.session_state.term_logs = seed_lines

    # Instantly add 2-3 log lines per autorefresh to make it feel super active
    for _ in range(random.randint(2, 4)):
        cls, msg  = _random_log_line(logs_df)
        st.session_state.term_logs.append((cls, msg))
    
    st.session_state.term_logs = st.session_state.term_logs[-40:]

    st.markdown(
        f'<div class="log-box">{_render_log_lines(st.session_state.term_logs)}</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div style="font-size:0.62rem; color:#00ff4144; letter-spacing:.2em; margin-top:4px;">'
        '▶ STREAM ACTIVE · auto-refresh every 2s</div>',
        unsafe_allow_html=True,
    )


# ── RIGHT: DETECTED THREATS TABLE ────────────────────────────
with col_threats:
    st.markdown('<div class="term-header">detected threats</div>', unsafe_allow_html=True)

    rows_html = ""
    for _, row in sorted_results.head(14).iterrows():
        label   = str(row["final_label"])
        color   = get_color(label)
        fused   = float(row.get("fused_score", row.get("risk_score", 0)))
        conf    = float(row.get("confidence",  0))
        action  = str(row.get("action", "LOG"))
        summary = str(row.get("summary", ""))
        bar     = ascii_bar(fused, width=10, color=color)
        conf_pct = f"{conf:.0%}"
        action_color = {"BLOCK": "#ff2222", "RATE_LIMIT": "#ffb000",
                        "ALERT": "#00ffff", "LOG": "#00ff4166"}.get(action, "#ffffff")

        rows_html += f"""
        <tr>
            <td style="color:{color}; font-family:'Share Tech Mono',monospace;
                font-size:0.7rem;">{row['api_key']}</td>
            <td><span class="pill pill-{label}">{label}</span></td>
            <td>{bar}</td>
            <td style="color:#aa66ff; text-align:center; font-size:0.7rem;">{conf_pct}</td>
            <td style="color:{action_color}; font-size:0.65rem; letter-spacing:.08em">{action}</td>
        </tr>"""

    st.markdown(f"""
    <div style="max-height:360px; overflow-y:auto; border:1px solid var(--border);
                border-radius:2px;">
    <table class="term-table">
        <thead><tr>
            <th>API KEY</th><th>LEVEL</th>
            <th>FUSED SCORE</th>
            <th style="text-align:center">CONF</th>
            <th>ACTION</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table></div>""", unsafe_allow_html=True)

st.markdown('<hr class="term-hr">', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  ▓▓  AI INSIGHT PANEL
# ──────────────────────────────────────────────────────────────

st.markdown('<div class="term-header">agent reasoning &amp; threat analysis</div>', unsafe_allow_html=True)

all_keys    = results_df["api_key"].tolist() if not results_df.empty else ["—"]
default_key = sorted_results.iloc[0]["api_key"] if not sorted_results.empty else all_keys[0]
default_idx = all_keys.index(default_key) if default_key in all_keys else 0
selected_key = st.selectbox("SELECT TARGET API KEY", options=all_keys, index=default_idx)

sel_row     = results_df[results_df["api_key"] == selected_key].iloc[0] if not results_df.empty else pd.Series()
color       = get_color(str(sel_row.get("final_label", "LOW")))
reasoning   = str(sel_row.get("reasoning",     "No reasoning trace available."))
action_rsn  = str(sel_row.get("action_reason", ""))
verdict     = str(sel_row.get("final_label",   "LOW"))
action      = str(sel_row.get("action",        "LOG"))
conf        = float(sel_row.get("confidence",  0.0))
fused       = float(sel_row.get("fused_score", sel_row.get("risk_score", 0)))
r_val       = int(sel_row.get("risk_score",    0))
a_val       = float(sel_row.get("anomaly_score", 0))
rep         = bool(sel_row.get("repeat_offender", False))
vel         = float(sel_row.get("request_velocity", 0.0))
obs         = int(sel_row.get("prior_observations", 0))

action_color = {"BLOCK": "#ff2222", "RATE_LIMIT": "#ffb000",
                "ALERT": "#00ffff", "LOG": "#00ff4188"}.get(action, "#ffffff")

ins_left, ins_right = st.columns([3, 1])

with ins_left:
    repeat_badge = (
        '<span style="color:#ff2222; border:1px solid #ff2222; padding:1px 7px; '
        'border-radius:2px; font-size:0.65rem; margin-left:10px">REPEAT OFFENDER</span>'
        if rep else ""
    )
    vel_badge = (
        f'<span style="color:#ffb000; border:1px solid #ffb000; padding:1px 7px; '
        f'border-radius:2px; font-size:0.65rem; margin-left:6px">VEL +{vel:.0f}</span>'
        if vel > 30 else ""
    )
    obs_txt = f'<span style="color:#00ff4155; font-size:0.62rem; margin-left:10px">{obs} prior obs</span>'

    st.markdown(f"""
    <div class="insight-panel" style="border-left-color:{color}">
        <div class="insight-hdr" style="margin-bottom:10px">
            ● AGENT REASONING TRACE &nbsp;·&nbsp;
            <span style="color:{color}">{selected_key}</span>
            {repeat_badge}{vel_badge}{obs_txt}
        </div>
        <div style="font-size:0.72rem; line-height:2.1; color:#ffffffcc;
                    border-bottom:1px solid #00ff4118; padding-bottom:10px; margin-bottom:10px">
            {reasoning}
        </div>
        <div style="font-size:0.65rem; color:#00ff4188; letter-spacing:.15em;
                    text-transform:uppercase; margin-bottom:4px">ACTION JUSTIFICATION</div>
        <div style="font-size:0.7rem; color:#ffffffaa">
            <span style="color:{action_color}; font-weight:bold">[{action}]</span>
            &nbsp;— {action_rsn}
        </div>
    </div>""", unsafe_allow_html=True)

with ins_right:
    r_bar = ascii_bar(r_val,  width=14, color=color)
    a_bar = ascii_bar(a_val,  width=14, color="#ffb000")
    c_bar = ascii_bar(conf * 100, width=14, color="#aa66ff")
    f_bar = ascii_bar(fused, width=14, color=color)

    st.markdown(f"""
    <div class="insight-panel" style="border-left-color:{color}; padding:12px 16px;">
        <div class="insight-hdr">VERDICT</div>
        <div style="font-family:'VT323',monospace; font-size:3.2rem; color:{color};
             text-shadow:0 0 20px {color}; line-height:1.1; margin-bottom:6px">{verdict}</div>
        <div style="font-family:'VT323',monospace; font-size:1.4rem;
             color:{action_color}; margin-bottom:12px; letter-spacing:.08em">{action}</div>
        <div style="font-size:0.6rem; color:#ffffff44; letter-spacing:.15em; margin-bottom:3px">FUSED SCORE</div>
        <div style="margin-bottom:7px">{f_bar}</div>
        <div style="font-size:0.6rem; color:#ffffff44; letter-spacing:.15em; margin-bottom:3px">CONFIDENCE</div>
        <div style="margin-bottom:7px">{c_bar}</div>
        <div style="font-size:0.6rem; color:#ffffff44; letter-spacing:.15em; margin-bottom:3px">RISK SCORE</div>
        <div style="margin-bottom:7px">{r_bar}</div>
        <div style="font-size:0.6rem; color:#ffffff44; letter-spacing:.15em; margin-bottom:3px">ANOMALY SCORE</div>
        <div>{a_bar}</div>
    </div>""", unsafe_allow_html=True)

st.markdown('<hr class="term-hr">', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  ▓▓  TOP THREAT REASONING TRACES  (HIGH keys only)
# ──────────────────────────────────────────────────────────────

high_decisions = [d for d in decisions if d.get("final_label") == "HIGH"][:4]

if high_decisions:
    st.markdown('<div class="term-header">top threat reasoning — agent decisions</div>',
                unsafe_allow_html=True)

    trace_cols = st.columns(min(len(high_decisions), 4))
    for col, d in zip(trace_cols, high_decisions):
        conf_val   = float(d.get("confidence", 0))
        fused_val  = float(d.get("fused_score", 0))
        rep_flag   = d.get("repeat_offender", False)
        trace_text = str(d.get("reasoning", ""))
        # Trim to the body part after the header bracket
        body_start = trace_text.find("] — ")
        body       = trace_text[body_start + 4:] if body_start >= 0 else trace_text
        action_c   = "#ff2222" if d["action"] == "BLOCK" else "#ffb000"

        rep_html = (
            '<div style="color:#ff2222; font-size:0.6rem; margin-top:3px; '
            'letter-spacing:.1em">REPEAT OFFENDER</div>'
            if rep_flag else ""
        )

        with col:
            st.markdown(f"""
            <div class="insight-panel" style="border-left-color:#ff2222; padding:10px 13px;">
                <div style="color:#ff2222; font-size:0.65rem; letter-spacing:.15em;
                     font-family:'Share Tech Mono',monospace; margin-bottom:5px">
                    {d['api_key']}
                </div>
                <div style="font-family:'VT323',monospace; font-size:1.5rem;
                     color:{action_c}; letter-spacing:.05em; margin-bottom:5px">
                    {d['action']} &nbsp;
                    <span style="font-size:0.8rem; color:#aa66ff">{conf_val:.0%} conf</span>
                </div>
                <div style="font-size:0.63rem; color:#ffffffaa; line-height:1.8;">
                    {body[:200]}{'...' if len(body) > 200 else ''}
                </div>
                {rep_html}
            </div>""", unsafe_allow_html=True)

    st.markdown('<hr class="term-hr">', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  ◓◓  ATTACK TYPES LIVE BREAKDOWN
# ──────────────────────────────────────────────────────────────

st.markdown('<div class="term-header">🔥 attack types detected this cycle</div>', unsafe_allow_html=True)

# Tally attack_type from fresh logs
if "attack_type" in logs_df.columns:
    type_counts = logs_df["attack_type"].value_counts().to_dict()
else:
    type_counts = {"normal": len(logs_df)}

ATTACK_META = {
    "normal":      {"color": "#00ff41", "icon": "✓",  "label": "NORMAL TRAFFIC"},
    "brute_force": {"color": "#ff2222", "icon": "✗",  "label": "BRUTE FORCE"},
    "scraping":    {"color": "#ffb000", "icon": "⛑",  "label": "API SCRAPING"},
    "ddos":        {"color": "#ff00ff", "icon": "☠",  "label": "DDoS FLOOD"},
}

atk_cols = st.columns(len(ATTACK_META))
for col, (atype, meta) in zip(atk_cols, ATTACK_META.items()):
    count = type_counts.get(atype, 0)
    share = int(count / max(len(logs_df), 1) * 100)
    bar   = ascii_bar(share, width=14, color=meta["color"])
    with col:
        st.markdown(f"""
        <div class="kpi-strip" style="border-left-color:{meta['color']}">
            <div class="kpi-val" style="color:{meta['color']}; text-shadow:0 0 10px {meta['color']}88">
                {meta['icon']} {count}
            </div>
            <div class="kpi-lbl">{meta['label']}</div>
            <div style="margin-top:6px">{bar}</div>
        </div>""", unsafe_allow_html=True)

# — Detection Alerts —
brute_count  = type_counts.get("brute_force", 0)
ddos_count   = type_counts.get("ddos", 0)
scrape_count = type_counts.get("scraping", 0)

if brute_count > 0:
    brute_keys = logs_df[logs_df["attack_type"] == "brute_force"]["api_key"].unique().tolist()
    st.error(f"⚠️ Brute force attack detected! {brute_count} login-hammering events from: {', '.join(brute_keys[:5])}")

if ddos_count > 0:
    ddos_keys = logs_df[logs_df["attack_type"] == "ddos"]["api_key"].unique().tolist()
    st.error(f"💥 DDoS flood detected! {ddos_count} volumetric burst events from: {', '.join(ddos_keys[:5])}")

if scrape_count > 0:
    st.warning(f"🔍 API scraping detected! {scrape_count} systematic sweep events flagged this cycle.")

# Live attack-type table
st.markdown(f"""
<table class="term-table" style="margin-top:10px">
<thead><tr>
    <th>ATTACK TYPE</th><th>COUNT</th><th>SHARE %</th><th>VISUAL</th>
</tr></thead>
<tbody>
{''.join(
    f'<tr><td style="color:{ATTACK_META.get(atype,{"color":"#ffffff"})["color"]}; font-weight:bold">{atype.upper()}</td>'
    f'<td style="color:#ffffffaa">{cnt}</td>'
    f'<td style="color:#ffffffaa">{int(cnt/max(len(logs_df),1)*100)}%</td>'
    f'<td>{ascii_bar(int(cnt/max(len(logs_df),1)*100), width=16, color=ATTACK_META.get(atype,{"color":"#ffffff"})["color"])}</td></tr>'
    for atype, cnt in sorted(type_counts.items(), key=lambda x: -x[1])
)}
</tbody></table>""", unsafe_allow_html=True)

st.markdown('<hr class="term-hr">', unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  ▓▓  FULL ROSTER  —  filterable
# ──────────────────────────────────────────────────────────────

st.markdown('<div class="term-header">full api key roster</div>', unsafe_allow_html=True)

filter_col, _ = st.columns([1, 3])
with filter_col:
    filter_lbl = st.selectbox("FILTER", ["ALL", "HIGH", "MEDIUM", "LOW"])

display_df = (results_df if filter_lbl == "ALL"
              else results_df[results_df["final_label"] == filter_lbl])
display_df = display_df.sort_values("risk_score", ascending=False).reset_index(drop=True)

roster_rows = ""
for _, row in display_df.iterrows():
    lbl    = str(row["final_label"])
    clr    = get_color(lbl)
    risk   = int(row.get("risk_score",    0))
    anom   = float(row.get("anomaly_score", 0))
    conf   = float(row.get("confidence",  0))
    action = str(row.get("action", "LOG"))
    summ   = str(row.get("summary", ""))
    bar    = ascii_bar(risk, width=12, color=clr)
    act_c  = {"BLOCK":"#ff2222","RATE_LIMIT":"#ffb000","ALERT":"#00ffff","LOG":"#00ff4155"}.get(action,"#fff")

    roster_rows += f"""
    <tr>
        <td style="color:{clr}; font-family:'Share Tech Mono',monospace;
            font-size:0.7rem;">{row['api_key']}</td>
        <td><span class="pill pill-{lbl}">{lbl}</span></td>
        <td>{bar}</td>
        <td style="color:#ffb000; text-align:right; font-size:0.7rem;">{anom}</td>
        <td style="color:#aa66ff; text-align:center; font-size:0.7rem;">{conf:.0%}</td>
        <td style="color:{act_c}; font-size:0.65rem; letter-spacing:.06em">{action}</td>
        <td style="color:#ffffff55; font-size:0.62rem; max-width:180px; overflow:hidden;
            text-overflow:ellipsis; white-space:nowrap;">{summ}</td>
    </tr>"""

st.markdown(f"""
<div style="max-height:300px; overflow-y:auto; border:1px solid var(--border);
            border-radius:2px;">
<table class="term-table">
    <thead><tr>
        <th>API KEY</th><th>THREAT LEVEL</th>
        <th>RISK SCORE</th><th style="text-align:right">ANOMALY</th>
        <th style="text-align:center">CONF</th>
        <th>ACTION</th><th>SUMMARY</th>
    </tr></thead>
    <tbody>{roster_rows}</tbody>
</table></div>""", unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  ▓▓  LIVE ALERTS + FIREWALL STATUS
# ──────────────────────────────────────────────────────────────

st.markdown('<div class="term-header">🚨 live alerts &amp; firewall</div>', unsafe_allow_html=True)

if len(alerts_this_cycle) > 0:
    st.warning("⚠️ SYSTEM UNDER ATTACK — automated blocking response engaged")

alert_col, block_col = st.columns([2, 1])

with alert_col:
    st.markdown("**🚨 ALERTS THIS CYCLE**")
    if not alerts_this_cycle:
        st.success("🟢 No HIGH-risk alerts this cycle — system clear.")
    else:
        for a in alerts_this_cycle[:8]:
            risk      = a.get('risk_score',    0)
            anom      = a.get('anomaly_score', 0)
            sev       = a.get('severity',      'CRITICAL')
            conf_a    = float(a.get('confidence', 0))
            reasoning_a = str(a.get('reasoning', ''))
            action_rsn_a = str(a.get('action_reason', ''))
            # Extract body after "] — "
            body_s    = reasoning_a.find("] — ")
            reason_body = reasoning_a[body_s + 4:] if body_s >= 0 else reasoning_a
            sev_color = {"CRITICAL": "#ff2222", "WARNING": "#ffb000", "INFO": "#00ffff"}.get(sev, "#ff2222")

            st.markdown(f"""
            <div class="insight-panel alert-card-live" style="border-left-color:{sev_color};
                 margin-bottom:8px; padding:10px 14px">
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:5px">
                    <span style="color:{sev_color}; font-weight:bold;
                        font-family:'Share Tech Mono',monospace; font-size:0.75rem">
                        [{sev}] {a['api_key']}</span>
                    <span style="color:#00ff4144; font-size:0.62rem">{a.get('timestamp','')}</span>
                </div>
                <div style="font-size:0.68rem; color:#ffffffaa; margin-bottom:5px">
                    Score: <span style="color:{sev_color}">{risk}</span>
                    &nbsp;·&nbsp; Anomaly: <span style="color:#ffb000">{anom}</span>
                    &nbsp;·&nbsp; Conf: <span style="color:#aa66ff">{conf_a:.0%}</span>
                    &nbsp;·&nbsp; <span style="color:{sev_color}; font-weight:bold">{a['action']}</span>
                </div>
                <div style="font-size:0.63rem; color:#ffffff88; line-height:1.8;
                     border-top:1px solid #ffffff11; padding-top:5px">
                    {reason_body[:280]}{'...' if len(reason_body) > 280 else ''}
                </div>
                <div style="font-size:0.62rem; color:#ffb00088; margin-top:4px">
                    {action_rsn_a}
                </div>
            </div>""", unsafe_allow_html=True)

with block_col:
    st.markdown("**⛔ BLOCKED KEYS (this session)**")
    if not blocked_this_session:
        st.markdown('<div style="color:#00ff4166; font-size:0.72rem; font-family:monospace">No keys blocked yet.</div>',
                    unsafe_allow_html=True)
    else:
        block_html = ""
        for key in blocked_this_session[:20]:
            block_html += (f'<div style="color:#ff2222; font-size:0.68rem; font-family:monospace; '
                           f'border-bottom:1px solid #ff222215; padding:3px 0;">⛔ {key}</div>')
        st.markdown(f"""
        <div style="background:#1a0000; border:1px solid #ff222233; border-radius:2px;
                    padding:10px 14px; max-height:260px; overflow-y:auto">
            {block_html}
        </div>
        <div style="font-size:0.62rem; color:#ff222266; margin-top:4px">
            {len(blocked_this_session)} key(s) firewalled this session</div>
        """, unsafe_allow_html=True)


# ──────────────────────────────────────────────────────────────
#  ▓▓  FOOTER
# ──────────────────────────────────────────────────────────────

st.markdown("""
<hr class="term-hr">
<div style="text-align:center; font-size:0.62rem; color:#00ff4133;
     letter-spacing:.3em; text-transform:uppercase; padding-bottom:1rem;
     font-family:'Share Tech Mono',monospace">
    VIGILAI &nbsp;·&nbsp; AUTONOMOUS SECURITY AGENT &nbsp;·&nbsp; OBSERVE · REASON · DECIDE · ACT
    &nbsp;·&nbsp; ISOLATION FOREST + RULE ENGINE + AGENTIC MEMORY &nbsp;·&nbsp; ALL SYSTEMS NOMINAL
</div>""", unsafe_allow_html=True)