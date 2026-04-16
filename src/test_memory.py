"""
Phase 1 verification — run from src/ directory:
    python test_memory.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from memory.short_term import ShortTermMemory
from memory.long_term  import LongTermMemory


def test_short_term():
    print("\n=== ShortTermMemory ===")
    stm = ShortTermMemory(window=5)

    key = "api_key_TEST"

    # Simulate 4 cycles of increasing load
    for i, avg in enumerate([10, 20, 35, 60]):
        stm.record(key, {"average_requests": avg, "total_requests": avg * 3})

    window = stm.get(key)
    print(f"  Window length : {len(window)} (expected 4)")
    assert len(window) == 4

    vel = stm.velocity(key, "average_requests")
    print(f"  Velocity      : {vel} (expected 50.0)")
    assert vel == 50.0, f"Got {vel}"

    avg = stm.avg(key, "average_requests")
    print(f"  Rolling avg   : {avg:.2f} (expected 31.25)")
    assert abs(avg - 31.25) < 0.01

    # Window cap — add a 6th record to a window=5 store
    stm2 = ShortTermMemory(window=3)
    for i in range(6):
        stm2.record("k2", {"average_requests": i * 10})
    assert len(stm2.get("k2")) == 3, "Window cap failed"
    print("  Window cap    : OK (capped at 3)")

    print("  PASS OK")


def test_long_term(tmp_path="data/memory/test_long_term.json"):
    print("\n=== LongTermMemory ===")
    ltm = LongTermMemory(path=tmp_path)

    key = "api_key_LTM"

    # 5 LOW observations
    for _ in range(5):
        ltm.update(key, {"average_requests": 20.0}, "LOW")

    baseline = ltm.get_baseline(key)
    print(f"  Observations  : {baseline['observations']} (expected 5)")
    assert baseline["observations"] == 5
    assert baseline["high_risk_count"] == 0
    assert not ltm.is_repeat_offender(key)
    print("  is_repeat_offender (0 HIGH): False OK")

    # 3 HIGH observations → becomes repeat offender
    for _ in range(3):
        ltm.update(key, {"average_requests": 90.0}, "HIGH")

    assert ltm.is_repeat_offender(key)
    print("  is_repeat_offender (3 HIGH): True  OK")

    # Deviation from baseline
    dev = ltm.deviation_from_baseline(key, current_avg=90.0)
    print(f"  Deviation from baseline: {dev:.1f}%")
    assert dev > 0

    # Persistence — reload from disk and check data survived
    ltm2 = LongTermMemory(path=tmp_path)
    assert ltm2.is_repeat_offender(key), "Persistence failed — data lost on reload"
    print("  Disk persistence: PASS OK")

    # Cleanup test file
    import os
    os.remove(tmp_path)
    print("  PASS OK")


if __name__ == "__main__":
    test_short_term()
    test_long_term()
    print("\n[Phase 1] All memory tests passed.\n")
