"""
simulator.py — API log generator.

Produces synthetic API request logs across four traffic patterns:
    normal      — varied endpoints, low volume, human timing
    brute_force — hammers /api/login at high frequency
    scraping    — sweeps all endpoints methodically
    ddos        — extreme-volume flood on high-cost endpoints
"""

import random
from datetime import datetime, timedelta

# ── Traffic distribution (must sum to 1.0) ────────────────────────────────
TRAFFIC_MIX: dict[str, float] = {
    "normal":      0.60,
    "brute_force": 0.15,
    "scraping":    0.15,
    "ddos":        0.10,
}

# ── API surface ────────────────────────────────────────────────────────────
ALL_ENDPOINTS = [
    "/api/login", "/api/logout", "/api/user/profile",
    "/api/products", "/api/products/search", "/api/checkout",
    "/api/orders", "/api/recommendations", "/api/reviews", "/api/admin/stats",
]
LOGIN_ENDPOINT = ["/api/login"]
DDOS_TARGETS   = ["/api/products", "/api/recommendations", "/api/login", "/api/orders"]

# ── Key pools ──────────────────────────────────────────────────────────────
NORMAL_KEYS = [f"user_key_{i:03d}"   for i in range(1, 61)]
BRUTE_KEYS  = [f"brute_key_{i:03d}"  for i in range(1, 11)]
SCRAPE_KEYS = [f"scrape_key_{i:03d}" for i in range(1, 11)]
DDOS_KEYS   = [f"ddos_key_{i:03d}"   for i in range(1,  6)]

# ── IP pools (by prefix) ───────────────────────────────────────────────────
NORMAL_IPS = ["192.168", "10.0",   "172.16"]
BRUTE_IPS  = ["45.33",   "91.121", "185.220"]
SCRAPE_IPS = ["198.51",  "203.0",  "104.21"]
DDOS_IPS   = ["5.188",   "194.165", "89.248"]


# ── Helpers ────────────────────────────────────────────────────────────────

def _random_ip(prefixes: list[str]) -> str:
    prefix = random.choice(prefixes)
    return f"{prefix}.{random.randint(1, 254)}.{random.randint(1, 254)}"


def _random_timestamp(base: datetime, spread_seconds: int) -> str:
    offset = random.randint(0, max(spread_seconds, 1))
    return (base + timedelta(seconds=offset)).strftime("%Y-%m-%d %H:%M:%S")


def _counts_to_ints(mix: dict, n: int) -> dict:
    counts  = {k: int(v * n) for k, v in mix.items()}
    diff    = n - sum(counts.values())
    counts[max(counts, key=counts.get)] += diff
    return counts


# ── Per-type log factories ─────────────────────────────────────────────────

def _make_normal_log(base: datetime) -> dict:
    return {
        "api_key":       random.choice(NORMAL_KEYS),
        "endpoint":      random.choice(ALL_ENDPOINTS),
        "request_count": random.randint(1, 15),
        "timestamp":     _random_timestamp(base, 3600),
        "ip_address":    _random_ip(NORMAL_IPS),
        "attack_type":   "normal",
    }


def _make_brute_force_log(base: datetime) -> dict:
    return {
        "api_key":       random.choice(BRUTE_KEYS),
        "endpoint":      random.choice(LOGIN_ENDPOINT),
        "request_count": random.randint(200, 800),
        "timestamp":     _random_timestamp(base, 300),
        "ip_address":    _random_ip(BRUTE_IPS),
        "attack_type":   "brute_force",
    }


def _make_scraping_log(base: datetime) -> dict:
    return {
        "api_key":       random.choice(SCRAPE_KEYS),
        "endpoint":      random.choice(ALL_ENDPOINTS),
        "request_count": random.randint(50, 300),
        "timestamp":     _random_timestamp(base, 1200),
        "ip_address":    _random_ip(SCRAPE_IPS),
        "attack_type":   "scraping",
    }


def _make_ddos_log(base: datetime) -> dict:
    return {
        "api_key":       random.choice(DDOS_KEYS),
        "endpoint":      random.choice(DDOS_TARGETS),
        "request_count": random.randint(1000, 5000),
        "timestamp":     _random_timestamp(base, 30),
        "ip_address":    _random_ip(DDOS_IPS),
        "attack_type":   "ddos",
    }


_FACTORIES = {
    "normal":      _make_normal_log,
    "brute_force": _make_brute_force_log,
    "scraping":    _make_scraping_log,
    "ddos":        _make_ddos_log,
}


# ── Public API ─────────────────────────────────────────────────────────────

def generate_logs(n: int) -> list[dict]:
    """
    Generate n synthetic API log entries using the current TRAFFIC_MIX.

    Returns a shuffled list of log dicts, each containing:
        api_key, endpoint, request_count, timestamp, ip_address, attack_type
    """
    if n < 1:
        raise ValueError("n must be a positive integer")

    base   = datetime.now()
    counts = _counts_to_ints(TRAFFIC_MIX, n)
    logs   = [
        _FACTORIES[attack_type](base)
        for attack_type, count in counts.items()
        for _ in range(count)
    ]
    random.shuffle(logs)
    return logs
