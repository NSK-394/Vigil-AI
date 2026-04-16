"""
simulator.py  (v2 — multi-pattern)
-----------------------------------
Simulates API request logs with four distinct traffic behaviours:

  NORMAL      — real human browsing, varied endpoints, low volume
  BRUTE_FORCE — hammers /api/login repeatedly at high frequency
  SCRAPING    — sweeps across every endpoint quickly, moderate counts
  DDOS        — floods any endpoint with an extreme burst of requests

Each log row now includes an "attack_type" field so downstream modules
(feature_extractor, risk_engine, detector) can use it as a ground-truth
label during training and evaluation.

Public API (unchanged from v1):
    generate_logs(n)  →  list[dict]
"""

import random
from datetime import datetime, timedelta


# ══════════════════════════════════════════════════════════════
#  CONFIGURATION  —  tweak ratios and thresholds here freely
# ══════════════════════════════════════════════════════════════

# How the n logs are split across the four behaviour types.
# Values must sum to 1.0.
TRAFFIC_MIX = {
    "normal":      0.60,   # 60% realistic human traffic
    "brute_force": 0.15,   # 15% credential-stuffing / login attacks
    "scraping":    0.15,   # 15% automated API scraping
    "ddos":        0.10,   # 10% volumetric DDoS bursts
}

# ── All endpoints the fake API exposes ──────────────────────────────────────
ALL_ENDPOINTS = [
    "/api/login",
    "/api/logout",
    "/api/user/profile",
    "/api/products",
    "/api/products/search",
    "/api/checkout",
    "/api/orders",
    "/api/recommendations",
    "/api/reviews",
    "/api/admin/stats",        # high-value target for scrapers
]

# ── Endpoint sub-groups used by specific attack types ───────────────────────
LOGIN_ENDPOINT   = ["/api/login"]         # brute-force only cares about this
DDOS_TARGETS     = ["/api/products", "/api/recommendations",
                    "/api/login",    "/api/orders"]   # high-cost endpoints

# ── API key pools ────────────────────────────────────────────────────────────
NORMAL_KEYS = [f"user_key_{i:03d}"   for i in range(1, 61)]   # 60 real users
BRUTE_KEYS  = [f"brute_key_{i:03d}"  for i in range(1, 11)]   # 10 brute-force IDs
SCRAPE_KEYS = [f"scrape_key_{i:03d}" for i in range(1, 11)]   # 10 scraper IDs
DDOS_KEYS   = [f"ddos_key_{i:03d}"   for i in range(1,  6)]   # 5 DDoS sources

# ── IP address pools ─────────────────────────────────────────────────────────
NORMAL_IPS  = ["192.168", "10.0",   "172.16"]   # private / residential
BRUTE_IPS   = ["45.33",   "91.121", "185.220"]  # VPN / Tor exit nodes
SCRAPE_IPS  = ["198.51",  "203.0",  "104.21"]   # cloud / datacenter
DDOS_IPS    = ["5.188",   "194.165","89.248"]   # botnet IP ranges


# ══════════════════════════════════════════════════════════════
#  HELPER UTILITIES
# ══════════════════════════════════════════════════════════════

def _random_ip(prefixes: list) -> str:
    """Build a plausible fake IP from a given prefix pool."""
    prefix = random.choice(prefixes)
    return f"{prefix}.{random.randint(1, 254)}.{random.randint(1, 254)}"


def _random_timestamp(base_time: datetime, spread_seconds: int) -> str:
    """
    Return a timestamp string offset randomly from base_time.

    spread_seconds controls how wide the time window is:
      - Large spread  →  traffic dribbles in over a long period (normal user)
      - Tiny spread   →  all requests crammed into a few seconds (DDoS burst)
    """
    offset = random.randint(0, max(spread_seconds, 1))
    return (base_time + timedelta(seconds=offset)).strftime("%Y-%m-%d %H:%M:%S")


def _counts_to_ints(mix: dict, n: int) -> dict:
    """
    Convert the TRAFFIC_MIX ratios into integer counts that sum exactly to n.
    The rounding remainder goes to the largest bucket.
    """
    counts  = {k: int(v * n) for k, v in mix.items()}
    diff    = n - sum(counts.values())
    biggest = max(counts, key=counts.get)
    counts[biggest] += diff
    return counts


# ══════════════════════════════════════════════════════════════
#  PER-TYPE LOG FACTORIES
#  Each function returns one fully-formed log dict.
# ══════════════════════════════════════════════════════════════

def _make_normal_log(base_time: datetime) -> dict:
    """
    Normal user log entry.

    Behaviour profile:
      - Browses a variety of endpoints — no single one dominates
      - Low request count per session  (1 – 15 requests)
      - Traffic spread across a ~60-minute window
      - Residential / private IP range
    """
    return {
        "api_key":       random.choice(NORMAL_KEYS),
        "endpoint":      random.choice(ALL_ENDPOINTS),   # diverse browsing
        "request_count": random.randint(1, 15),           # human-scale volume
        "timestamp":     _random_timestamp(base_time, spread_seconds=3600),
        "ip_address":    _random_ip(NORMAL_IPS),
        "attack_type":   "normal",
    }


def _make_brute_force_log(base_time: datetime) -> dict:
    """
    Brute-force / credential-stuffing log entry.

    Behaviour profile:
      - Hammers ONLY /api/login — no interest in other endpoints
      - Very high request count per burst  (200 – 800)
      - Rapid-fire timestamps compressed into ~5-minute window
      - IP from known VPN / Tor exit-node ranges
    """
    return {
        "api_key":       random.choice(BRUTE_KEYS),
        "endpoint":      random.choice(LOGIN_ENDPOINT),   # laser-focused on login
        "request_count": random.randint(200, 800),         # hundreds of attempts
        "timestamp":     _random_timestamp(base_time, spread_seconds=300),
        "ip_address":    _random_ip(BRUTE_IPS),
        "attack_type":   "brute_force",
    }


def _make_scraping_log(base_time: datetime) -> dict:
    """
    API scraping log entry.

    Behaviour profile:
      - Hits EVERY endpoint systematically — broad coverage, not depth
      - Moderate request count per endpoint  (50 – 300)
      - Medium time window ~20 minutes (methodical, not rushed)
      - Datacenter / cloud IP — scrapers rarely use residential IPs
    """
    return {
        "api_key":       random.choice(SCRAPE_KEYS),
        "endpoint":      random.choice(ALL_ENDPOINTS),    # sweeps all routes
        "request_count": random.randint(50, 300),          # moderate per-endpoint
        "timestamp":     _random_timestamp(base_time, spread_seconds=1200),
        "ip_address":    _random_ip(SCRAPE_IPS),
        "attack_type":   "scraping",
    }


def _make_ddos_log(base_time: datetime) -> dict:
    """
    DDoS burst log entry.

    Behaviour profile:
      - Floods high-cost endpoints with extreme volume
      - Astronomical request count  (1000 – 5000 per burst)
      - Timestamps squeezed into a ~30-second window — pure flood
      - Botnet IP ranges (suspicious ASNs)
    """
    return {
        "api_key":       random.choice(DDOS_KEYS),
        "endpoint":      random.choice(DDOS_TARGETS),     # high-cost endpoints
        "request_count": random.randint(1000, 5000),       # extreme volume
        "timestamp":     _random_timestamp(base_time, spread_seconds=30),
        "ip_address":    _random_ip(DDOS_IPS),
        "attack_type":   "ddos",
    }


# Dispatch table — attack_type string → factory function
_FACTORIES = {
    "normal":      _make_normal_log,
    "brute_force": _make_brute_force_log,
    "scraping":    _make_scraping_log,
    "ddos":        _make_ddos_log,
}


# ══════════════════════════════════════════════════════════════
#  MAIN PUBLIC FUNCTION
# ══════════════════════════════════════════════════════════════

def generate_logs(n: int) -> list:
    """
    Generate n simulated API log entries with mixed traffic patterns.

    Parameters
    ----------
    n : int
        Total number of log entries to produce.

    Returns
    -------
    list[dict]
        Shuffled list of log dicts.  Each dict has:
            api_key       – identifies the caller
            endpoint      – API route that was hit
            request_count – number of requests in this log entry
            timestamp     – datetime string  (YYYY-MM-DD HH:MM:SS)
            ip_address    – source IP
            attack_type   – "normal" | "brute_force" | "scraping" | "ddos"

    Traffic split (set via TRAFFIC_MIX at the top of this file):
        normal 60%  ·  brute_force 15%  ·  scraping 15%  ·  ddos 10%

    Example
    -------
    >>> logs = generate_logs(1000)
    >>> logs[0]
    {'api_key': 'user_key_023', 'endpoint': '/api/products',
     'request_count': 8, 'timestamp': '2024-06-01 14:32:11',
     'ip_address': '192.168.4.201', 'attack_type': 'normal'}
    """
    if n < 1:
        raise ValueError("n must be a positive integer")

    base_time = datetime.now()   # all timestamps are anchored to this moment

    # ── Step 1: Decide exact count for each attack type ──────────────────
    counts = _counts_to_ints(TRAFFIC_MIX, n)
    # Example for n=1000:
    # {'normal': 600, 'brute_force': 150, 'scraping': 150, 'ddos': 100}

    # ── Step 2: Generate logs for every type ─────────────────────────────
    logs = []
    for attack_type, count in counts.items():
        factory = _FACTORIES[attack_type]    # look up the right builder
        for _ in range(count):
            logs.append(factory(base_time))

    # ── Step 3: Shuffle so types are interleaved realistically ───────────
    # Real log files don't group all bots together.
    random.shuffle(logs)

    return logs


# ══════════════════════════════════════════════════════════════
#  QUICK DEMO  —  runs only when executed directly
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import collections

    N = 200
    logs = generate_logs(N)

    # ── Distribution breakdown ────────────────────────────────────────────
    type_counts = collections.Counter(log["attack_type"] for log in logs)

    print(f"\ngenerate_logs({N})  →  {N} entries\n")
    print(f"{'ATTACK TYPE':<14}  {'COUNT':>5}  {'SHARE':>6}  VISUAL")
    print("─" * 50)
    for atype in ["normal", "brute_force", "scraping", "ddos"]:
        count = type_counts[atype]
        share = count / N * 100
        bar   = "█" * int(share / 2)
        print(f"{atype:<14}  {count:>5}  {share:>5.1f}%  {bar}")

    # ── One sample row per attack type ───────────────────────────────────
    print("\n── Sample row per attack type ───────────────────────────────────")
    seen = set()
    for log in logs:
        t = log["attack_type"]
        if t not in seen:
            seen.add(t)
            print(
                f"  [{t}]\n"
                f"    key={log['api_key']:<16}  ep={log['endpoint']:<26}"
                f"  req={log['request_count']:<5}  ip={log['ip_address']}"
            )
        if len(seen) == 4:
            break

    # ── Request count ranges per type ────────────────────────────────────
    print("\n── Request count stats per attack type ──────────────────────────")
    by_type: dict = collections.defaultdict(list)
    for log in logs:
        by_type[log["attack_type"]].append(log["request_count"])

    for atype in ["normal", "brute_force", "scraping", "ddos"]:
        reqs = by_type[atype]
        print(f"  {atype:<14}  min={min(reqs):<5}  max={max(reqs):<5}  "
              f"avg={sum(reqs)/len(reqs):.1f}")