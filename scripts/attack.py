"""
scripts/attack.py — Attack traffic generator for VigilAI real-traffic mode.

Fires rapid requests at the FastAPI ingestion server to trigger detections.

Usage:
    python scripts/attack.py --mode brute_force --target http://localhost:8000
    python scripts/attack.py --mode scraping    --requests 200
    python scripts/attack.py --mode ddos        --concurrency 20
    python scripts/attack.py --mode all         --target http://localhost:8000

Requires: pip install httpx
"""

from __future__ import annotations

import argparse
import asyncio
import random
import time

import httpx

# ── Attack profiles ───────────────────────────────────────────────────────────

ENDPOINTS = [
    "/api/login", "/api/products", "/api/user",
    "/api/search", "/api/orders",
]

PROFILES: dict[str, dict] = {
    "brute_force": {
        "endpoints":   ["/api/login"],
        "api_keys":    [f"brute_key_{i:03d}" for i in range(1, 6)],
        "requests":    300,
        "concurrency": 10,
        "delay":       0.01,
        "description": "High-frequency login hammering (credential stuffing)",
    },
    "scraping": {
        "endpoints":   ENDPOINTS,
        "api_keys":    [f"scrape_key_{i:03d}" for i in range(1, 4)],
        "requests":    200,
        "concurrency": 5,
        "delay":       0.05,
        "description": "Systematic endpoint sweep (data harvesting)",
    },
    "ddos": {
        "endpoints":   ["/api/products", "/api/orders"],
        "api_keys":    [f"ddos_key_{i:03d}" for i in range(1, 3)],
        "requests":    500,
        "concurrency": 25,
        "delay":       0.0,
        "description": "High-volume flood (volumetric DDoS)",
    },
    "normal": {
        "endpoints":   ENDPOINTS,
        "api_keys":    [f"user_key_{i:03d}" for i in range(1, 20)],
        "requests":    80,
        "concurrency": 3,
        "delay":       0.1,
        "description": "Baseline normal traffic",
    },
}


# ── Core ──────────────────────────────────────────────────────────────────────

async def _send(client: httpx.AsyncClient, base_url: str, profile: dict, sem: asyncio.Semaphore):
    async with sem:
        api_key  = random.choice(profile["api_keys"])
        endpoint = random.choice(profile["endpoints"])
        headers  = {"x-api-key": api_key, "User-Agent": "VigilAI-AttackSim/1.0"}
        try:
            await client.get(f"{base_url}{endpoint}", headers=headers, timeout=5.0)
        except httpx.RequestError:
            pass
        if profile["delay"] > 0:
            await asyncio.sleep(profile["delay"])


async def run_attack(mode: str, base_url: str, n_requests: int, concurrency: int):
    profile = {**PROFILES[mode]}
    if n_requests:
        profile["requests"] = n_requests
    if concurrency:
        profile["concurrency"] = concurrency

    print(f"\n[VigilAI Attack Sim] mode={mode.upper()}")
    print(f"  {profile['description']}")
    print(f"  target={base_url}  requests={profile['requests']}  concurrency={profile['concurrency']}")
    print(f"  keys={profile['api_keys'][:3]}{'...' if len(profile['api_keys']) > 3 else ''}\n")

    sem   = asyncio.Semaphore(profile["concurrency"])
    start = time.perf_counter()

    async with httpx.AsyncClient() as client:
        tasks = [
            _send(client, base_url, profile, sem)
            for _ in range(profile["requests"])
        ]
        await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start
    rps     = profile["requests"] / elapsed
    print(f"  Done: {profile['requests']} requests in {elapsed:.2f}s ({rps:.0f} req/s)")


async def run_all(base_url: str):
    for mode in ("normal", "scraping", "brute_force", "ddos"):
        await run_attack(mode, base_url, n_requests=0, concurrency=0)
        await asyncio.sleep(1)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="VigilAI attack traffic generator")
    parser.add_argument("--mode",        default="brute_force",
                        choices=[*PROFILES.keys(), "all"],
                        help="Attack pattern to simulate")
    parser.add_argument("--target",      default="http://localhost:8000",
                        help="Base URL of the FastAPI ingestion server")
    parser.add_argument("--requests",    type=int, default=0,
                        help="Override request count (0 = use profile default)")
    parser.add_argument("--concurrency", type=int, default=0,
                        help="Override concurrency (0 = use profile default)")
    args = parser.parse_args()

    if args.mode == "all":
        asyncio.run(run_all(args.target))
    else:
        asyncio.run(run_attack(args.mode, args.target, args.requests, args.concurrency))


if __name__ == "__main__":
    main()
