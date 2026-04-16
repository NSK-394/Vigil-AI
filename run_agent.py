"""
run_agent.py — VigilAI Autonomous Agent CLI
============================================
Runs the agent loop continuously in the terminal without the dashboard.
Each cycle prints a live SOC-style report: stats, top threats, reasoning traces.

Usage:
    python run_agent.py                      # default: normal traffic, infinite
    python run_agent.py --mode attack        # attack traffic preset
    python run_agent.py --cycles 5           # run exactly 5 cycles then exit
    python run_agent.py --mode suspicious --cycles 10 --interval 2
"""

import sys
import os
import time
import argparse

# Make src/ importable from project root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from core.agent_loop import AgentLoop


# ── Colour codes (ANSI) ──────────────────────────────────────────────────
R  = "\033[91m"    # red
Y  = "\033[93m"    # yellow / amber
G  = "\033[92m"    # green
C  = "\033[96m"    # cyan
M  = "\033[95m"    # magenta / purple
DG = "\033[2;32m"  # dim green
W  = "\033[97m"    # white
RS = "\033[0m"     # reset
B  = "\033[1m"     # bold


# ── Traffic presets ───────────────────────────────────────────────────────
PRESETS = {
    "normal":     {"normal": 0.85, "brute_force": 0.05, "scraping": 0.07, "ddos": 0.03},
    "suspicious": {"normal": 0.55, "brute_force": 0.20, "scraping": 0.18, "ddos": 0.07},
    "attack":     {"normal": 0.20, "brute_force": 0.35, "scraping": 0.25, "ddos": 0.20},
}


def label_color(label: str) -> str:
    return {"HIGH": R, "MEDIUM": Y, "LOW": G}.get(label, W)


def action_color(action: str) -> str:
    return {"BLOCK": R, "RATE_LIMIT": Y, "ALERT": C, "LOG": DG}.get(action, W)


def ascii_bar(value: float, width: int = 20) -> str:
    filled = int((value / 100) * width)
    return G + "█" * filled + DG + "░" * (width - filled) + RS


def print_header(cycle: int, mode: str, now: str) -> None:
    print(f"\n{DG}{'─' * 72}{RS}")
    print(
        f"  {B}{G}💀 VigilAI Agent Loop{RS}  "
        f"{DG}cycle #{cycle}{RS}  "
        f"{DG}{now}{RS}  "
        f"mode: {B}{Y if mode != 'normal' else G}{mode.upper()}{RS}"
    )
    print(f"{DG}{'─' * 72}{RS}")


def print_stats(stats: dict) -> None:
    h = stats.get("high",          0)
    m = stats.get("medium",        0)
    l = stats.get("low",           0)
    b = stats.get("blocked",       0)
    a = stats.get("alerts_fired",  0)
    c = stats.get("avg_confidence", 0.0)
    k = stats.get("total_keys",    0)

    print(
        f"\n  {DG}KEYS{RS} {W}{k}{RS}  "
        f"{R}HIGH {h}{RS}  "
        f"{Y}MED {m}{RS}  "
        f"{G}LOW {l}{RS}  "
        f"{R}BLOCKED {b}{RS}  "
        f"{C}ALERTS {a}{RS}  "
        f"{M}CONF {c:.0%}{RS}"
    )


def print_threats(decisions: list, max_show: int = 6) -> None:
    highs = [d for d in decisions if d["final_label"] == "HIGH"][:max_show]
    if not highs:
        print(f"\n  {G}No HIGH-risk keys this cycle — system clear.{RS}")
        return

    print(f"\n  {B}{R}TOP THREATS{RS}")
    print(f"  {DG}{'API KEY':<20} {'LEVEL':<8} {'FUSED':>6} {'CONF':>6} {'ACTION':<12} SUMMARY{RS}")
    print(f"  {DG}{'─' * 68}{RS}")

    for d in highs:
        lc  = label_color(d["final_label"])
        ac  = action_color(d["action"])
        bar = ascii_bar(d["fused_score"], width=10)
        print(
            f"  {lc}{d['api_key']:<20}{RS} "
            f"{lc}{d['final_label']:<8}{RS} "
            f"{bar} "
            f"{M}{d['confidence']:.0%}{RS:>4}  "
            f"{ac}{d['action']:<12}{RS} "
            f"{DG}{d.get('summary','')}{RS}"
        )


def print_reasoning(decisions: list, max_traces: int = 3) -> None:
    highs = [d for d in decisions if d["final_label"] == "HIGH"][:max_traces]
    if not highs:
        return

    print(f"\n  {B}{C}AGENT REASONING TRACES{RS}")
    for d in highs:
        reasoning = d.get("reasoning", "")
        body_start = reasoning.find("] — ")
        body = reasoning[body_start + 4:] if body_start >= 0 else reasoning

        rep_flag = "  [REPEAT OFFENDER]" if d.get("repeat_offender") else ""
        print(f"\n  {R}{d['api_key']}{RS}{R}{rep_flag}{RS}")
        print(f"  {DG}{reasoning.split('] — ')[0]}]{RS}")

        # Break reasoning body into clauses and print each indented
        for clause in body.rstrip(".").split("; "):
            print(f"    {DG}›{RS} {W}{clause.strip()}{RS}")

        act_rsn = d.get("action_reason", "")
        if act_rsn:
            ac = action_color(d["action"])
            print(f"    {ac}→ {d['action']}: {act_rsn}{RS}")


def print_alerts(alerts: list, max_show: int = 4) -> None:
    if not alerts:
        return
    print(f"\n  {B}{R}ALERTS FIRED{RS}")
    for a in alerts[:max_show]:
        sev_c = {"CRITICAL": R, "WARNING": Y, "INFO": C}.get(a.get("severity",""), W)
        print(
            f"  {sev_c}[{a.get('severity','?')}]{RS} "
            f"{a['api_key']:<20} "
            f"{action_color(a['action'])}{a['action']:<12}{RS} "
            f"risk={a['risk_score']:>3}  "
            f"conf={float(a.get('confidence', 0)):.0%}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="VigilAI Autonomous Agent CLI")
    parser.add_argument("--mode",     default="normal",
                        choices=["normal", "suspicious", "attack"],
                        help="Traffic scenario preset")
    parser.add_argument("--cycles",   type=int, default=0,
                        help="Number of cycles to run (0 = infinite)")
    parser.add_argument("--interval", type=float, default=3.0,
                        help="Seconds between cycles (default: 3)")
    parser.add_argument("--logs",     type=int, default=100,
                        help="Log entries per cycle (default: 100)")
    args = parser.parse_args()

    os.makedirs("data/memory", exist_ok=True)
    loop = AgentLoop(
        ltm_path="data/memory/long_term.json",
        results_path="data/results.csv",
    )

    print(f"\n{B}{G}VigilAI Autonomous Security Agent{RS}")
    print(f"{DG}Mode: {args.mode}  |  Logs/cycle: {args.logs}  |  Interval: {args.interval}s{RS}")
    print(f"{DG}Press Ctrl+C to stop.{RS}")

    cycle = 0
    try:
        while True:
            cycle += 1
            now = time.strftime("%Y-%m-%d %H:%M:%S")

            result = loop.run(n_logs=args.logs, traffic_mix=PRESETS[args.mode])

            print_header(cycle, args.mode, now)
            print_stats(result["stats"])
            print_threats(result["decisions"])
            print_reasoning(result["decisions"])
            print_alerts(result["alerts"])

            if args.cycles and cycle >= args.cycles:
                print(f"\n{G}Completed {cycle} cycle(s). Exiting.{RS}\n")
                break

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print(f"\n\n{DG}Agent loop stopped after {cycle} cycle(s).{RS}\n")


if __name__ == "__main__":
    main()
