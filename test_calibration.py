"""
Proves the calibration system does something real: an agent that has been
overconfident in the past should have its future confidence claims
automatically discounted, and the calibration report should honestly
surface that overconfidence rather than hiding it.
"""

import asyncio
import os
from agent.core.calibration import CalibrationTracker


async def main():
    log_path = "/tmp_calib_test.jsonl" if os.path.exists("/tmp") and os.access("/", os.W_OK) else "./calib_test.jsonl"
    log_path = "./calib_test.jsonl"
    if os.path.exists(log_path):
        os.remove(log_path)

    tracker = CalibrationTracker(log_path)

    print("=== Simulating an overconfident agent's track record ===")
    # Agent claims 0.9 confidence 10 times, but is only actually right 4/10.
    # A real agent (or person) would call this overconfident. Let's prove
    # the tracker catches it instead of taking the stated number at face value.
    outcomes = [True, False, False, True, False, False, True, False, False, False]
    indices = []
    for i, outcome in enumerate(outcomes):
        idx = tracker.predict(f"task_{i}", confidence=0.9)
        indices.append(idx)
        tracker.resolve(idx, outcome)

    report = tracker.calibration_report()
    print(f"Resolved predictions: {report['resolved_count']}")
    print(f"Overall calibration error: {report['overall_calibration_error']}")
    for bucket, stats in report["buckets"].items():
        print(f"  {bucket}: stated={stats['stated_confidence_avg']}, "
              f"actual={stats['actual_success_rate']}, error={stats['calibration_error']}")

    assert report["overall_calibration_error"] > 0.3, \
        "Calibration report should clearly flag this as badly miscalibrated"
    print("PASS: report honestly shows the agent was overconfident (0.9 claimed, 0.4 actual)")

    print("\n=== Discount factor derived from that track record ===")
    discount = tracker.suggested_discount()
    print(f"Suggested discount multiplier: {discount}")
    assert discount < 1.0, "An overconfident track record must produce a discount below 1.0"
    print(f"PASS: future confidence claims will be multiplied by {discount}, not taken at face value")

    print("\n=== Applying the discount to a new claim ===")
    new_raw_confidence = 0.9
    adjusted = round(new_raw_confidence * discount, 3)
    print(f"Agent claims {new_raw_confidence} confidence on a new task")
    print(f"After track-record correction: {adjusted}")
    assert adjusted < new_raw_confidence
    print("PASS: the agent's own history pulled its overconfident claim back down")

    print("\n=== Well-calibrated case (control) ===")
    log_path2 = "./calib_test_good.jsonl"
    if os.path.exists(log_path2):
        os.remove(log_path2)
    good_tracker = CalibrationTracker(log_path2)
    # Claims 0.7 confidence, right 7/10 times - actually well calibrated.
    good_outcomes = [True, True, True, True, True, True, True, False, False, False]
    for i, outcome in enumerate(good_outcomes):
        idx = good_tracker.predict(f"good_task_{i}", confidence=0.7)
        good_tracker.resolve(idx, outcome)
    good_report = good_tracker.calibration_report()
    print(f"Overall calibration error: {good_report['overall_calibration_error']}")
    good_discount = good_tracker.suggested_discount()
    print(f"Suggested discount: {good_discount}")
    assert good_report["overall_calibration_error"] < 0.1
    assert 0.9 <= good_discount <= 1.1
    print("PASS: well-calibrated track record leaves confidence claims roughly untouched")

    os.remove(log_path)
    os.remove(log_path2)
    print("\n=== ALL CALIBRATION CHECKS PASSED ===")


if __name__ == "__main__":
    asyncio.run(main())

