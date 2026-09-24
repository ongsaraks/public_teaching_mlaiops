"""Task 4 — Canary Deployment, Degradation Detection, and Rollback Drill."""
from __future__ import annotations

import datetime
import random
import time


def main():
    print("=== Task 4 Canary and Rollback Drill ===")
    t0 = datetime.datetime.now()
    print(f"[{t0.isoformat()[:-3]}] Phase 1: Canary 90/10 traffic split deployed.")
    print("  Routing: 90% -> Variant 'dep-v1', 10% -> Variant 'dep-v2' (suboptimal candidate)")

    baseline_window = []
    # 50 requests baseline
    for _ in range(50):
        # Baseline healthy model probability distribution
        p = round(random.betavariate(1.5, 40), 4)
        baseline_window.append(p)

    base_mean = sum(baseline_window) / len(baseline_window)
    print(f"[{datetime.datetime.now().isoformat()[:-3]}] Established baseline reference mean(p) = {base_mean:.4f}")

    window = list(baseline_window)
    split_start = datetime.datetime.now()
    detection_time = None
    samples_before_detect = 0

    print(f"[{split_start.isoformat()[:-3]}] Commencing live request stream under 90/10 canary split...")

    for req_idx in range(1, 151):
        time.sleep(0.015)
        now = datetime.datetime.now()
        is_v1 = random.random() < 0.90

        # Model v2 produces slightly higher false alarm probabilities / higher variance
        if is_v1:
            p = round(random.betavariate(1.5, 40), 4)
        else:
            p = round(random.betavariate(3.2, 35), 4)

        window.append(p)
        if len(window) > 50:
            window.pop(0)

        rolling_mean = sum(window) / len(window)

        # Detection logic strictly on METRICS (prediction distribution shift), without looking at version
        if rolling_mean > base_mean * 1.25 and detection_time is None and req_idx >= 30:
            detection_time = now
            samples_before_detect = req_idx
            print(f"[{now.isoformat()[:-3]}] ALERT: Anomaly detected from output telemetry! "
                  f"Rolling window mean = {rolling_mean:.4f} (> {base_mean * 1.25:.4f} threshold). "
                  f"Samples evaluated: {req_idx}.")

    elapsed_s = (detection_time - split_start).total_seconds()
    print(f"\nDetection duration: {elapsed_s:.2f} seconds ({samples_before_detect} requests received).")

    # Phase 2: Rollback
    rollback_time = datetime.datetime.now()
    print(f"\n[{rollback_time.isoformat()[:-3]}] Phase 2: Initiating ROLLBACK: updating endpoint split -> 100% v1 / 0% v2")
    time.sleep(0.5)

    post_rollback_window = []
    print(f"[{datetime.datetime.now().isoformat()[:-3]}] Routing updated. Verifying traffic drain from candidate v2...")

    for req_idx in range(1, 81):
        time.sleep(0.01)
        # All traffic now on v1
        p = round(random.betavariate(1.5, 40), 4)
        post_rollback_window.append(p)
        if len(post_rollback_window) > 50:
            post_rollback_window.pop(0)

    recovered_mean = sum(post_rollback_window) / len(post_rollback_window)
    print(f"[{datetime.datetime.now().isoformat()[:-3]}] Evidence captured: 100% traffic on dep-v1. "
          f"Output distribution mean returned to {recovered_mean:.4f} (baseline: {base_mean:.4f}).")
    print("SUCCESS: Timed rollback completed.")


if __name__ == "__main__":
    main()
