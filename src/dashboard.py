"""
dashboard.py — VigilAI SOC Dashboard

Professional real-time API threat monitoring.
Run: streamlit run src/dashboard.py
"""

import sys
import os
import html
import random
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from streamlit_autorefresh import st_autorefresh

_src_dir = os.path.dirname(os.path.abspath(__file__))
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

from core.agent_loop import AgentLoop
from alert_system    import get_blocked_keys

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title="VigilAI · SOC Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st_autorefresh(interval=3000, key="dashboard_refresh")

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
    --bg:        #0d1117;
    --bg2:       #161b22;
    --bg3:       #1c2128;
    --border:    #30363d;
    --text:      #e6edf3;
    --muted:     #7d8590;
    --green:     #3fb950;
    --yellow:    #d29922;
    --red:       #f85149;
    --blue:      #58a6ff;
    --purple:    #bc8cff;
}

/* Hide Streamlit chrome */
#MainMenu, footer, header,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"],
[data-testid="stSidebar"],
section[data-testid="stSidebar"] { display: none !important; }

html, body,
[data-testid="stAppViewContainer"],
[data-testid="stMain"], .main {
    background: var(--bg) !important;
    color: var(--text) !important;
    font-family: 'Inter', system-ui, sans-serif !important;
}
.block-container {
    padding: 1rem 2rem 2rem !important;
    max-width: 100% !important;
}

/* Headings */
.section-header {
    font-size: 0.7rem;
    font-weight: 600;
    color: var(--muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    padding-bottom: 6px;
    margin: 20px 0 12px;
}

/* Top bar */
.topbar-title {
    font-size: 1.4rem;
    font-weight: 600;
    color: var(--text);
    letter-spacing: -0.01em;
}
.topbar-sub {
    font-size: 0.75rem;
    color: var(--muted);
    margin-top: 2px;
}

/* Mode badge */
.mode-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    letter-spacing: 0.04em;
    border: 1px solid;
}
.mode-normal     { color: var(--green);  border-color: #3fb95055; background: #3fb95012; }
.mode-suspicious { color: var(--yellow); border-color: #d2992255; background: #d2992212; }
.mode-attack     { color: var(--red);    border-color: #f8514955; background: #f8514912; }

/* Status dot */
.dot-green  { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--green); }
.dot-yellow { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--yellow); }
.dot-red    { display:inline-block; width:7px; height:7px; border-radius:50%; background:var(--red); }

/* KPI cards */
.kpi-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 14px 16px;
    text-align: center;
}
.kpi-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 2rem;
    font-weight: 500;
    line-height: 1.1;
}
.kpi-lbl {
    font-size: 0.64rem;
    color: var(--muted);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-top: 4px;
}

/* Threat table */
.soc-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.78rem;
    font-family: 'JetBrains Mono', monospace;
}
.soc-table th {
    color: var(--muted);
    font-size: 0.65rem;
    font-weight: 500;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    border-bottom: 1px solid var(--border);
    padding: 8px 10px;
    text-align: left;
}
.soc-table td {
    padding: 7px 10px;
    border-bottom: 1px solid #30363d44;
    color: var(--text);
    vertical-align: middle;
}
.soc-table tr:hover td { background: #ffffff06; }

/* Pills */
.pill {
    display: inline-block;
    padding: 1px 8px;
    border-radius: 4px;
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.06em;
    font-family: 'JetBrains Mono', monospace;
}
.pill-HIGH   { color: var(--red);    background: #f8514918; border: 1px solid #f8514944; }
.pill-MEDIUM { color: var(--yellow); background: #d2992218; border: 1px solid #d2992244; }
.pill-LOW    { color: var(--green);  background: #3fb95018; border: 1px solid #3fb95044; }

/* Action badge */
.act-BLOCK      { color: var(--red);    font-weight: 600; }
.act-RATE_LIMIT { color: var(--yellow); }
.act-ALERT      { color: var(--blue);  }
.act-LOG        { color: var(--muted); }

/* Score bar */
.score-bar-wrap { display: flex; align-items: center; gap: 8px; }
.score-bar-bg   { flex: 1; height: 4px; background: #30363d; border-radius: 2px; }
.score-bar-fill { height: 4px; border-radius: 2px; }
.score-num      { font-size: 0.68rem; color: var(--muted); width: 28px; text-align: right;
                  font-family: 'JetBrains Mono', monospace; }

/* Insight panel */
.insight-panel {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-left: 3px solid var(--blue);
    border-radius: 6px;
    padding: 14px 16px;
    font-size: 0.78rem;
    color: var(--text);
    line-height: 1.7;
}
.insight-label {
    font-size: 0.64rem;
    color: var(--muted);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: 6px;
    font-weight: 600;
}

/* Alert card */
.alert-card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-left: 3px solid;
    border-radius: 6px;
    padding: 10px 14px;
    margin-bottom: 8px;
    font-size: 0.75rem;
}

/* Log box */
.log-box {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 14px;
    height: 320px;
    overflow-y: auto;
    font-size: 0.72rem;
    font-family: 'JetBrains Mono', monospace;
    line-height: 1.8;
}
.log-box::-webkit-scrollbar       { width: 4px; }
.log-box::-webkit-scrollbar-track { background: transparent; }
.log-box::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
.log-ok     { color: var(--green); }
.log-warn   { color: var(--yellow); }
.log-alert  { color: var(--red); }
.log-info   { color: var(--blue); }
.log-muted  { color: var(--muted); font-style: italic; }
.log-ts     { color: #30363d; margin-right: 8px; }

/* Scenario buttons — active state highlight */
.btn-active-normal     [data-testid="stButton"] > button { border-color: var(--green)  !important; color: var(--green)  !important; }
.btn-active-suspicious [data-testid="stButton"] > button { border-color: var(--yellow) !important; color: var(--yellow) !important; }
.btn-active-attack     [data-testid="stButton"] > button { border-color: var(--red)    !important; color: var(--red)    !important; }

[data-testid="stButton"] > button {
    background: var(--bg3) !important;
    color: var(--muted) !important;
    border: 1px solid var(--border) !important;
    font-family: 'Inter', sans-serif !important;
    font-size: 0.75rem !important;
    font-weight: 500 !important;
    border-radius: 6px !important;
    transition: border-color 0.15s, color 0.15s !important;
    padding: 6px 14px !important;
}
[data-testid="stButton"] > button:hover {
    border-color: var(--blue) !important;
    color: var(--text) !important;
    background: var(--bg2) !important;
}

/* Selectbox */
[data-testid="stSelectbox"] label p {
    color: var(--muted) !important;
    font-size: 0.68rem !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    font-family: 'Inter', sans-serif !important;
}

/* Divider */
.divider { border: none; border-top: 1px solid var(--border); margin: 16px 0; }

/* Firewall list */
.blocked-key {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.72rem;
    color: var(--red);
    padding: 4px 0;
    border-bottom: 1px solid #f8514914;
}
</style>
""", unsafe_allow_html=True)


# ── Constants ─────────────────────────────────────────────────────────────────

TRAFFIC_PRESETS = {
    "normal":     {"normal": 0.85, "brute_force": 0.05, "scraping": 0.07, "ddos": 0.03},
    "suspicious": {"normal": 0.55, "brute_force": 0.20, "scraping": 0.18, "ddos": 0.07},
    "attack":     {"normal": 0.20, "brute_force": 0.35, "scraping": 0.25, "ddos": 0.20},
}

ATTACK_META = {
    "normal":      {"color": "#3fb950", "label": "Normal"},
    "brute_force": {"color": "#f85149", "label": "Brute Force"},
    "scraping":    {"color": "#d29922", "label": "Scraping"},
    "ddos":        {"color": "#bc8cff", "label": "DDoS"},
}

LOG_POOL = [
    ("log-muted", "watchdog: ping OK — all monitors healthy"),
    ("log-muted", "gc: buffer rotated, 1024 entries flushed"),
    ("log-info",  "ingest: {req} events received from {ip}"),
    ("log-info",  "parse: api_key={key}  endpoint={ep}  count={req}"),
    ("log-info",  "model: IsolationForest re-scored {key}"),
    ("log-info",  "engine: rule pipeline processed {req} events"),
    ("log-ok",    "pass: {key} — volume within threshold"),
    ("log-ok",    "pass: {key} — endpoint diversity OK"),
    ("log-ok",    "clear: {key} — both engines report LOW"),
    ("log-warn",  "watch: {key} — elevated request rate"),
    ("log-warn",  "scan: {key} — repeated access to {ep}"),
    ("log-warn",  "proto: unusual user-agent pattern from {ip}"),
    ("log-alert", "threat: {key} — anomaly score CRITICAL"),
    ("log-alert", "block: rate-limiting applied → {ip}"),
    ("log-alert", "detect: {key} hammering {ep} · {req} hits/min"),
]


# ── State initialisation ──────────────────────────────────────────────────────

def _init_state():
    if "mode" not in st.session_state:
        st.session_state.mode = "normal"
    if "source" not in st.session_state:
        st.session_state.source = "simulated"   # "simulated" | "real"
    if "agent_loop" not in st.session_state:
        os.makedirs("data/memory", exist_ok=True)
        st.session_state["agent_loop"] = AgentLoop(
            ltm_path="data/memory/long_term.json",
            results_path="data/results.csv",
        )
    if "term_logs" not in st.session_state:
        st.session_state["term_logs"] = []
    if "cycle" not in st.session_state:
        st.session_state["cycle"] = 0
    if "high_history" not in st.session_state:
        st.session_state["high_history"] = []
    if "prev_stats" not in st.session_state:
        st.session_state["prev_stats"] = {}
    if "session_totals" not in st.session_state:
        st.session_state["session_totals"] = {"high": 0, "alerts": 0}

_init_state()


# ── Run one agent cycle ───────────────────────────────────────────────────────

def _run_cycle() -> dict:
    loop   = st.session_state["agent_loop"]
    mode   = st.session_state.mode
    source = st.session_state.source
    os.makedirs("data", exist_ok=True)
    # traffic_mix only applies in simulated mode; ignored when source="real"
    mix = TRAFFIC_PRESETS[mode] if source == "simulated" else None
    try:
        result = loop.run(n_logs=100, traffic_mix=mix, source=source)
        st.session_state["cycle"] += 1
        return result
    except Exception as e:
        return {"logs": [], "decisions": [], "alerts": [], "stats": {}, "features": [], "error": str(e)}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _label_color(label: str) -> str:
    return {"HIGH": "#f85149", "MEDIUM": "#d29922", "LOW": "#3fb950"}.get(str(label).upper(), "#e6edf3")

def _sparkline(values: list) -> str:
    """Render a list of ints as a Unicode block sparkline."""
    if not values:
        return ""
    blocks = "▁▂▃▄▅▆▇█"
    peak = max(values) if max(values) > 0 else 1
    return "".join(blocks[min(int(v / peak * 7), 7)] for v in values)

def _action_cls(action: str) -> str:
    return f"act-{action}" if action in ("BLOCK", "RATE_LIMIT", "ALERT", "LOG") else "act-LOG"

def _score_bar(value: float, color: str) -> str:
    pct = max(0.0, min(100.0, float(value)))
    return (
        f'<div class="score-bar-wrap">'
        f'<div class="score-bar-bg"><div class="score-bar-fill" '
        f'style="width:{pct}%; background:{color}"></div></div>'
        f'<span class="score-num">{int(pct)}</span>'
        f'</div>'
    )

def _random_log_line(logs_df: pd.DataFrame) -> tuple[str, str]:
    cls, tpl = random.choice(LOG_POOL)
    if not logs_df.empty:
        row = logs_df.sample(1).iloc[0]
        key = str(row.get("api_key", "key_???"))
        ep  = str(row.get("endpoint", "/api/???"))
        ip  = str(row.get("ip_address", "0.0.0.0"))
        req = str(row.get("request_count", "?"))
    else:
        key, ep, ip, req = "key_001", "/api/login", "192.168.1.1", "5"
    return cls, tpl.format(key=key, ep=ep, ip=ip, req=req)

def _update_term_logs(logs_df: pd.DataFrame):
    for _ in range(random.randint(1, 3)):
        cls, msg = _random_log_line(logs_df)
        st.session_state["term_logs"].append((cls, msg))
    st.session_state["term_logs"] = st.session_state["term_logs"][-50:]

def _render_log_html(lines: list) -> str:
    now = datetime.now()
    _out = ""
    for i, (cls, msg) in enumerate(lines):
        ts = (now - timedelta(seconds=len(lines) - i)).strftime("%H:%M:%S")
        _out += f'<div class="{cls}"><span class="log-ts">[{ts}]</span>{html.escape(msg)}</div>'
    return _out


# ── Section renderers ─────────────────────────────────────────────────────────

def render_topbar(mode: str, cycle: int, total_keys: int, high_history: list, session_totals: dict):
    now = datetime.now()
    mode_meta = {
        "normal":     ("mode-normal",     "● Normal"),
        "suspicious": ("mode-suspicious", "● Suspicious"),
        "attack":     ("mode-attack",     "● Under Attack"),
    }
    badge_cls, badge_txt = mode_meta[mode]
    spark = _sparkline(high_history[-16:]) if high_history else "—"
    ses_high   = session_totals.get("high", 0)
    ses_alerts = session_totals.get("alerts", 0)

    col_title, col_mode, col_status = st.columns([3.5, 2.0, 1.4])

    with col_title:
        st.markdown(f"""
        <div class="topbar-title">🛡️ VigilAI</div>
        <div class="topbar-sub">
            Autonomous API Threat Detection &nbsp;·&nbsp;
            {now.strftime("%Y-%m-%d %H:%M:%S")} &nbsp;·&nbsp; Cycle #{cycle}
        </div>
        <div style="margin-top:6px; font-family:'JetBrains Mono',monospace; font-size:0.68rem;
                    color:var(--muted); letter-spacing:0.04em">
            HIGH trend:
            <span style="color:#f85149; letter-spacing:0.02em">{spark}</span>
            &nbsp;·&nbsp; session threats:
            <span style="color:#f85149">{ses_high}</span>
            &nbsp;·&nbsp; alerts:
            <span style="color:#d29922">{ses_alerts}</span>
        </div>""", unsafe_allow_html=True)

    with col_mode:
        st.markdown(f"""
        <div style="padding-top:10px">
            <div class="mode-badge {badge_cls}">{badge_txt}</div>
            <div style="font-size:0.62rem; color:var(--muted); margin-top:5px">
                Monitoring {total_keys} keys · 3s refresh
            </div>
        </div>""", unsafe_allow_html=True)

    with col_status:
        try:
            from live_queue import queue_size as _qs
            _q = _qs()
            _queue_line = f'QUEUE: <span style="color:{"var(--green)" if _q == 0 else "var(--yellow)"}">{_q} pending</span><br>'
        except Exception:
            _queue_line = ""
        st.markdown(f"""
        <div style="text-align:right; padding-top:10px; font-size:0.72rem; color:var(--muted);
                    font-family:'JetBrains Mono',monospace; line-height:2">
            STATUS: <span style="color:var(--green); font-weight:600">ONLINE</span><br>
            {_queue_line}LAST SCAN: {now.strftime("%H:%M:%S")}
        </div>""", unsafe_allow_html=True)


def render_kpi_strip(total_keys, high_count, medium_count, low_count, total_reqs, avg_conf, prev: dict | None = None):
    prev = prev or {}
    def _delta(cur: int | float, key: str, fmt: str = "d") -> str:
        if key not in prev:
            return ""
        d = cur - prev[key]
        if d == 0:
            return '<div style="font-size:0.6rem; color:var(--muted); margin-top:2px">— same</div>'
        color = "#f85149" if d > 0 else "#3fb950"
        arrow = "▲" if d > 0 else "▼"
        val   = f"{d:+d}" if fmt == "d" else f"{d:+.0%}"
        return f'<div style="font-size:0.6rem; color:{color}; margin-top:2px">{arrow} {val}</div>'

    kpis = [
        (str(total_keys),   "Keys Monitored", "#58a6ff", _delta(total_keys,   "total_keys")),
        (str(high_count),   "High Threats",   "#f85149", _delta(high_count,   "high")),
        (str(medium_count), "Medium",         "#d29922", _delta(medium_count, "medium")),
        (str(low_count),    "Clear",          "#3fb950", _delta(low_count,    "low")),
        (f"{total_reqs:,}", "Total Requests", "#7d8590", _delta(total_reqs,   "total_reqs")),
        (f"{avg_conf:.0%}", "Avg Confidence", "#bc8cff", _delta(avg_conf,     "avg_conf", "f")),
    ]
    cols = st.columns(6)
    for col, (val, lbl, color, delta_html) in zip(cols, kpis):
        with col:
            st.markdown(f"""
            <div class="kpi-card">
                <div class="kpi-val" style="color:{color}">{val}</div>
                <div class="kpi-lbl">{lbl}</div>
                {delta_html}
            </div>""", unsafe_allow_html=True)


def render_threat_table(sorted_results: pd.DataFrame):
    if sorted_results.empty:
        st.markdown('<div style="color:var(--muted); font-size:0.75rem; padding:8px 0">'
                    'Waiting for data…</div>', unsafe_allow_html=True)
        return
    rows_html = ""
    for _, row in sorted_results.head(15).iterrows():
        label  = str(row["final_label"])
        color  = _label_color(label)
        fused  = float(row.get("fused_score", row.get("risk_score", 0)))
        conf   = float(row.get("confidence", 0))
        action = str(row.get("action", "LOG"))
        bar    = _score_bar(fused, color)
        rows_html += f"""
        <tr>
            <td style="font-family:'JetBrains Mono',monospace; font-size:0.73rem;
                color:{color}">{html.escape(str(row['api_key']))}</td>
            <td><span class="pill pill-{label}">{label}</span></td>
            <td>{bar}</td>
            <td style="text-align:center; color:#bc8cff; font-family:'JetBrains Mono',monospace;
                font-size:0.72rem">{conf:.0%}</td>
            <td class="{_action_cls(action)}" style="font-size:0.72rem">{html.escape(action)}</td>
        </tr>"""

    st.markdown(f"""
    <div style="max-height:350px; overflow-y:auto; border:1px solid var(--border); border-radius:6px;">
    <table class="soc-table">
        <thead><tr>
            <th>API KEY</th><th>LEVEL</th><th>SCORE</th>
            <th style="text-align:center">CONF</th><th>ACTION</th>
        </tr></thead>
        <tbody>{rows_html}</tbody>
    </table></div>""", unsafe_allow_html=True)


def render_terminal(logs_df: pd.DataFrame):
    _update_term_logs(logs_df)
    _content = _render_log_html(st.session_state["term_logs"])
    st.markdown(f'<div class="log-box">{_content}</div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size:0.62rem; color:var(--muted); margin-top:4px">'
                '▶ live stream · auto-refresh 3s</div>', unsafe_allow_html=True)


def render_insight_panel(results_df: pd.DataFrame):
    if results_df.empty:
        st.info("No data yet.")
        return

    all_keys    = results_df["api_key"].tolist()
    high_keys   = results_df[results_df["final_label"] == "HIGH"]["api_key"].tolist()
    default_key = high_keys[0] if high_keys else all_keys[0]
    default_idx = all_keys.index(default_key) if default_key in all_keys else 0

    selected_key = st.selectbox("Select API Key", options=all_keys, index=default_idx,
                                label_visibility="collapsed")
    row = results_df[results_df["api_key"] == selected_key].iloc[0]

    label      = str(row.get("final_label", "LOW")).upper()
    color      = _label_color(label)
    reasoning  = str(row.get("reasoning",     "No reasoning trace available."))
    action_rsn = str(row.get("action_reason", ""))
    action     = str(row.get("action",        "LOG"))
    conf       = float(row.get("confidence",  0.0))
    fused      = float(row.get("fused_score", row.get("risk_score", 0)))
    r_val      = float(row.get("risk_score",    0))
    a_val      = float(row.get("anomaly_score", 0))
    rep        = bool(row.get("repeat_offender", False))
    vel        = float(row.get("request_velocity", 0.0))
    obs        = int(row.get("prior_observations", 0))

    action_color = {"BLOCK":"#f85149","RATE_LIMIT":"#d29922","ALERT":"#58a6ff","LOG":"#7d8590"}.get(action,"#e6edf3")

    left, right = st.columns([3, 1])

    with left:
        tags = ""
        if rep:
            tags += '<span style="color:#f85149; border:1px solid #f8514944; padding:1px 6px; border-radius:4px; font-size:0.63rem; margin-left:8px">REPEAT OFFENDER</span>'
        if vel > 30:
            tags += f'<span style="color:#d29922; border:1px solid #d2992244; padding:1px 6px; border-radius:4px; font-size:0.63rem; margin-left:6px">VEL +{vel:.0f}</span>'
        if obs:
            tags += f'<span style="color:var(--muted); font-size:0.63rem; margin-left:8px">{obs} observations</span>'

        # strip the "[LABEL | conf=X | fused=Y] — " header; handle encoding variants of em dash
        _sep = next((s for s in ("] — ", "] – ", "] � ", "] - ") if s in reasoning), None)
        reason_body = reasoning[reasoning.index(_sep) + len(_sep):] if _sep else reasoning
        reason_body = html.escape(reason_body)

        st.markdown(f"""
        <div class="insight-panel" style="border-left-color:{color}">
            <div class="insight-label">
                Agent Reasoning Trace &nbsp;·&nbsp;
                <span style="color:{color}; font-family:'JetBrains Mono',monospace">{html.escape(selected_key)}</span>
                {tags}
            </div>
            <div style="line-height:1.8; color:var(--text); border-bottom:1px solid var(--border);
                        padding-bottom:10px; margin-bottom:10px">
                {reason_body}
            </div>
            <div class="insight-label">Action Justification</div>
            <div style="font-size:0.75rem;">
                <span style="color:{action_color}; font-weight:600">[{html.escape(action)}]</span>
                &nbsp;— {html.escape(action_rsn)}
            </div>
        </div>""", unsafe_allow_html=True)

    with right:
        st.markdown(f"""
        <div class="insight-panel" style="border-left-color:{color}; text-align:center; padding:16px">
            <div class="insight-label">Verdict</div>
            <div style="font-size:2rem; font-weight:700; color:{color}; line-height:1.1;
                        margin-bottom:4px">{label}</div>
            <div style="font-size:0.9rem; color:{action_color}; font-weight:600;
                        margin-bottom:16px">{action}</div>
            <div class="insight-label" style="text-align:left">Fused</div>
            <div style="margin-bottom:8px">{_score_bar(fused, color)}</div>
            <div class="insight-label" style="text-align:left">Confidence</div>
            <div style="margin-bottom:8px">{_score_bar(conf * 100, "#bc8cff")}</div>
            <div class="insight-label" style="text-align:left">Risk</div>
            <div style="margin-bottom:8px">{_score_bar(r_val, color)}</div>
            <div class="insight-label" style="text-align:left">Anomaly</div>
            <div>{_score_bar(a_val, "#d29922")}</div>
        </div>""", unsafe_allow_html=True)


def render_attack_breakdown(logs_df: pd.DataFrame):
    type_counts = logs_df["attack_type"].value_counts().to_dict() if "attack_type" in logs_df.columns else {}
    total       = max(len(logs_df), 1)
    cols        = st.columns(len(ATTACK_META))
    for col, (atype, meta) in zip(cols, ATTACK_META.items()):
        count = type_counts.get(atype, 0)
        pct   = int(count / total * 100)
        with col:
            st.markdown(f"""
            <div class="kpi-card" style="border-left:3px solid {meta['color']}">
                <div class="kpi-val" style="color:{meta['color']}; font-size:1.6rem">{count}</div>
                <div class="kpi-lbl">{meta['label']}</div>
                <div style="margin-top:8px">{_score_bar(pct, meta['color'])}</div>
            </div>""", unsafe_allow_html=True)


def render_high_traces(decisions: list):
    high = [d for d in decisions if d.get("final_label") == "HIGH"][:4]
    if not high:
        return
    st.markdown('<div class="section-header">Top Threat Traces</div>', unsafe_allow_html=True)
    cols = st.columns(min(len(high), 4))
    for col, d in zip(cols, high):
        conf   = float(d.get("confidence", 0))
        action = d.get("action", "BLOCK")
        action_color = "#f85149" if action == "BLOCK" else "#d29922"
        reasoning = str(d.get("reasoning", ""))
        _sep = next((s for s in ("] — ", "] – ", "] � ", "] - ") if s in reasoning), None)
        body = html.escape(reasoning[reasoning.index(_sep) + len(_sep):] if _sep else reasoning)
        rep_html = ('<div style="color:#f85149; font-size:0.62rem; margin-top:4px; font-weight:600">'
                    'REPEAT OFFENDER</div>' if d.get("repeat_offender") else "")
        with col:
            st.markdown(f"""
            <div class="insight-panel" style="border-left-color:#f85149; padding:10px 12px">
                <div style="font-family:'JetBrains Mono',monospace; font-size:0.7rem;
                    color:#f85149; margin-bottom:4px">{html.escape(str(d['api_key']))}</div>
                <div style="font-size:0.8rem; font-weight:600; color:{action_color};
                    margin-bottom:6px">{action}
                    <span style="color:#bc8cff; font-size:0.7rem; font-weight:400">
                    {conf:.0%} conf</span></div>
                <div style="font-size:0.68rem; color:var(--muted); line-height:1.7">
                    {body[:220]}{'…' if len(body) > 220 else ''}
                </div>
                {rep_html}
            </div>""", unsafe_allow_html=True)


def render_roster(results_df: pd.DataFrame):
    filter_col, _ = st.columns([1, 4])
    with filter_col:
        f = st.selectbox("Filter by level", ["ALL", "HIGH", "MEDIUM", "LOW"],
                         label_visibility="collapsed")
    df = (results_df if f == "ALL" else results_df[results_df["final_label"] == f])
    if df.empty or "risk_score" not in df.columns:
        st.markdown('<div style="color:var(--muted); font-size:0.75rem; padding:8px 0">'
                    'No data for this cycle.</div>', unsafe_allow_html=True)
        return
    df = df.sort_values("risk_score", ascending=False).reset_index(drop=True)

    rows = ""
    for _, row in df.iterrows():
        lbl    = str(row["final_label"])
        color  = _label_color(lbl)
        risk   = float(row.get("risk_score", 0))
        anom   = float(row.get("anomaly_score", 0))
        conf   = float(row.get("confidence", 0))
        action = str(row.get("action", "LOG"))
        summ   = str(row.get("summary", ""))
        rows += f"""
        <tr>
            <td style="font-family:'JetBrains Mono',monospace; color:{color}; font-size:0.73rem">{html.escape(str(row['api_key']))}</td>
            <td><span class="pill pill-{lbl}">{lbl}</span></td>
            <td>{_score_bar(risk, color)}</td>
            <td style="font-family:'JetBrains Mono',monospace; color:#d29922; text-align:right; font-size:0.72rem">{int(anom)}</td>
            <td style="font-family:'JetBrains Mono',monospace; color:#bc8cff; text-align:center; font-size:0.72rem">{conf:.0%}</td>
            <td class="{_action_cls(action)}" style="font-size:0.72rem">{html.escape(action)}</td>
            <td style="color:var(--muted); font-size:0.68rem; max-width:160px; overflow:hidden;
                text-overflow:ellipsis; white-space:nowrap">{html.escape(summ)}</td>
        </tr>"""

    st.markdown(f"""
    <div style="max-height:280px; overflow-y:auto; border:1px solid var(--border); border-radius:6px;">
    <table class="soc-table">
        <thead><tr>
            <th>API KEY</th><th>LEVEL</th><th>RISK</th>
            <th style="text-align:right">ANOMALY</th>
            <th style="text-align:center">CONF</th>
            <th>ACTION</th><th>SUMMARY</th>
        </tr></thead>
        <tbody>{rows}</tbody>
    </table></div>""", unsafe_allow_html=True)


def render_alerts(alerts: list, blocked_keys: list):
    alert_col, block_col = st.columns([2, 1])

    with alert_col:
        st.markdown('<div style="font-size:0.78rem; font-weight:600; color:var(--text); '
                    'margin-bottom:8px">Alerts This Cycle</div>', unsafe_allow_html=True)
        if not alerts:
            st.markdown('<div style="color:var(--green); font-size:0.75rem; padding:8px 0">'
                        '✓ No HIGH-risk alerts — system clear.</div>', unsafe_allow_html=True)
        else:
            for a in alerts[:8]:
                sev       = a.get("severity", "CRITICAL")
                sev_color = {"CRITICAL":"#f85149","WARNING":"#d29922","INFO":"#58a6ff"}.get(sev,"#f85149")
                reasoning = str(a.get("reasoning", ""))
                _sep = next((s for s in ("] — ", "] – ", "] � ", "] - ") if s in reasoning), None)
                body = html.escape(reasoning[reasoning.index(_sep) + len(_sep):] if _sep else reasoning)
                st.markdown(f"""
                <div class="alert-card" style="border-left-color:{sev_color}">
                    <div style="display:flex; justify-content:space-between; margin-bottom:4px">
                        <span style="color:{sev_color}; font-weight:600; font-size:0.75rem">
                            [{sev}] {html.escape(a['api_key'])}</span>
                        <span style="color:var(--muted); font-size:0.65rem">{a.get('timestamp','')}</span>
                    </div>
                    <div style="font-size:0.7rem; color:var(--muted); margin-bottom:4px">
                        Risk: <span style="color:{sev_color}">{a.get('risk_score',0)}</span>
                        &nbsp;·&nbsp; Anomaly: <span style="color:#d29922">{a.get('anomaly_score',0)}</span>
                        &nbsp;·&nbsp; Conf: <span style="color:#bc8cff">{float(a.get('confidence',0)):.0%}</span>
                        &nbsp;·&nbsp; <span style="color:{sev_color}; font-weight:600">{html.escape(a['action'])}</span>
                    </div>
                    <div style="font-size:0.68rem; color:var(--muted); line-height:1.7;
                        border-top:1px solid var(--border); padding-top:4px">
                        {body[:260]}{'…' if len(body) > 260 else ''}
                    </div>
                </div>""", unsafe_allow_html=True)

    with block_col:
        st.markdown('<div style="font-size:0.78rem; font-weight:600; color:var(--text); '
                    'margin-bottom:8px">Blocked Keys</div>', unsafe_allow_html=True)
        if not blocked_keys:
            st.markdown('<div style="color:var(--muted); font-size:0.75rem">No keys blocked yet.</div>',
                        unsafe_allow_html=True)
        else:
            items = "".join(f'<div class="blocked-key">⊘ {html.escape(k)}</div>' for k in blocked_keys[:20])
            st.markdown(f"""
            <div style="background:var(--bg2); border:1px solid var(--border); border-radius:6px;
                        padding:10px 14px; max-height:260px; overflow-y:auto">
                {items}
            </div>
            <div style="font-size:0.65rem; color:var(--muted); margin-top:6px">
                {len(blocked_keys)} key(s) blocked this session</div>""", unsafe_allow_html=True)


# ── Main layout ───────────────────────────────────────────────────────────────
# All buttons MUST come before _run_cycle() so clicks are captured this frame.

_c1, _c2, _c3, _spacer, _src_col = st.columns([1, 1, 1, 0.3, 1.4])
with _c1:
    if st.button("Normal", key="btn_normal", use_container_width=True):
        st.session_state.mode = "normal"
with _c2:
    if st.button("Suspicious", key="btn_sus", use_container_width=True):
        st.session_state.mode = "suspicious"
with _c3:
    if st.button("Attack", key="btn_attack", use_container_width=True):
        st.session_state.mode = "attack"
with _src_col:
    _src_label = "🟢 Real Traffic" if st.session_state.source == "real" else "⚙️ Simulated"
    if st.button(_src_label, key="btn_source", use_container_width=True):
        st.session_state.source = "real" if st.session_state.source == "simulated" else "simulated"

result    = _run_cycle()
source    = st.session_state.source
_is_empty = not result.get("decisions")

# When real-traffic buffer is empty, fall back to the last known good result
# so the dashboard doesn't go blank between request bursts.
if _is_empty and "last_result" in st.session_state:
    result    = st.session_state["last_result"]
    _stale    = True
elif not _is_empty:
    st.session_state["prev_stats"] = dict(st.session_state.get("_cur_stats", {}))
    st.session_state["last_result"] = result
    _stale = False
else:
    _stale = False

logs_df    = pd.DataFrame(result.get("logs", []))
results_df = pd.DataFrame(result.get("decisions", []))
decisions  = result.get("decisions", [])
alerts     = result.get("alerts", [])
stats      = result.get("stats", {})
blocked    = st.session_state["agent_loop"].blocked_keys()
mode       = st.session_state.mode
cycle      = st.session_state["cycle"]

high_count   = int((results_df["final_label"] == "HIGH").sum())   if not results_df.empty else 0
medium_count = int((results_df["final_label"] == "MEDIUM").sum()) if not results_df.empty else 0
low_count    = int((results_df["final_label"] == "LOW").sum())    if not results_df.empty else 0
total_keys   = len(results_df)
total_reqs   = int(logs_df["request_count"].sum()) if "request_count" in logs_df.columns else 0
avg_conf     = float(stats.get("avg_confidence", 0.0))

# Accumulate session totals and history on fresh cycles only
if not _stale and not _is_empty:
    st.session_state["_cur_stats"] = {
        "total_keys": total_keys, "high": high_count, "medium": medium_count,
        "low": low_count, "total_reqs": total_reqs, "avg_conf": avg_conf,
    }
    _hs = st.session_state["high_history"]
    _hs.append(high_count)
    if len(_hs) > 30:
        _hs.pop(0)
    st.session_state["session_totals"]["high"]   += high_count
    st.session_state["session_totals"]["alerts"] += len(alerts)

label_order    = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
sorted_results = results_df.copy()
if not sorted_results.empty and "final_label" in sorted_results.columns and "risk_score" in sorted_results.columns:
    sorted_results["_ord"] = sorted_results["final_label"].map(label_order)
    sorted_results = sorted_results.sort_values(["_ord", "risk_score"],
                                                ascending=[True, False]).drop(columns="_ord")

# Error banner — show if cycle raised an exception
if result.get("error"):
    st.markdown(f"""
    <div style="background:#1c2128; border:1px solid #f85149; border-left:3px solid #f85149;
                border-radius:6px; padding:10px 16px; font-size:0.78rem; color:#f85149; margin-bottom:8px">
        ⚠️ <strong>Agent cycle error</strong> — {html.escape(str(result['error']))}
    </div>""", unsafe_allow_html=True)

# Status banner — real-traffic waiting / stale notice
if source == "real" and _is_empty and "last_result" not in st.session_state:
    st.markdown("""
    <div style="background:#1c2128; border:1px solid #d29922; border-left:3px solid #d29922;
                border-radius:6px; padding:10px 16px; font-size:0.78rem; color:#d29922; margin-bottom:8px">
        ⚠️ <strong>Real Traffic mode</strong> — buffer empty. Start the FastAPI server and send requests:<br>
        <code style="color:#e6edf3; font-size:0.72rem">uvicorn src.api_server:app --port 8000</code>
        &nbsp;·&nbsp;
        <code style="color:#e6edf3; font-size:0.72rem">python scripts/attack.py --mode all</code>
    </div>""", unsafe_allow_html=True)
elif source == "real" and _stale:
    st.markdown("""
    <div style="background:#1c2128; border:1px solid #30363d; border-left:3px solid #58a6ff;
                border-radius:6px; padding:8px 16px; font-size:0.72rem; color:#7d8590; margin-bottom:8px">
        🕐 Real Traffic — showing last cycle's data · waiting for new requests
    </div>""", unsafe_allow_html=True)

# ── Render ────────────────────────────────────────────────────────────────────

render_topbar(mode, cycle, total_keys,
              high_history=st.session_state["high_history"],
              session_totals=st.session_state["session_totals"])
st.markdown('<hr class="divider">', unsafe_allow_html=True)

render_kpi_strip(total_keys, high_count, medium_count, low_count, total_reqs, avg_conf,
                 prev=st.session_state["prev_stats"])
st.markdown('<hr class="divider">', unsafe_allow_html=True)

col_log, col_table = st.columns([1, 1], gap="large")
with col_log:
    st.markdown('<div class="section-header">Live Event Stream</div>', unsafe_allow_html=True)
    render_terminal(logs_df)
with col_table:
    st.markdown('<div class="section-header">Detected Threats</div>', unsafe_allow_html=True)
    render_threat_table(sorted_results)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown('<div class="section-header">Agent Reasoning &amp; Analysis</div>', unsafe_allow_html=True)
render_insight_panel(results_df)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown('<div class="section-header">Traffic Breakdown</div>', unsafe_allow_html=True)
render_attack_breakdown(logs_df)

render_high_traces(decisions)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown('<div class="section-header">Full API Key Roster</div>', unsafe_allow_html=True)
render_roster(results_df)

st.markdown('<hr class="divider">', unsafe_allow_html=True)

st.markdown('<div class="section-header">Live Alerts &amp; Firewall</div>', unsafe_allow_html=True)
render_alerts(alerts, blocked)

st.markdown("""
<hr class="divider">
<div style="text-align:center; font-size:0.65rem; color:var(--muted); padding-bottom:1rem;
     letter-spacing:0.08em; text-transform:uppercase">
    VigilAI &nbsp;·&nbsp; Autonomous Security Agent &nbsp;·&nbsp;
    Observe · Reason · Decide · Act &nbsp;·&nbsp;
    IsolationForest + Rule Engine + Agentic Memory
</div>""", unsafe_allow_html=True)
