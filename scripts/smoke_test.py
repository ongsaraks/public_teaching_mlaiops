"""Smoke test the deployed or local inference service with 3 known payloads."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", default="http://localhost:8080")
    args = ap.parse_args()

    base_url = args.target.rstrip("/")
    print(f"Smoke testing target: {base_url}")

    # Payload 1: Normal valid payload
    p1 = {
        "temp_c": 78.4,
        "vibration_mm_s": 3.1,
        "pressure_kpa": 315.2,
        "hours_since_service": 4200.0,
        "load_pct": 68.0,
        "ambient_humidity": 55.0,
    }
    r1 = requests.post(f"{base_url}/predict", json=p1, timeout=10)
    print(f"Payload 1 (Normal): status={r1.status_code}, body={r1.text}")
    assert r1.status_code == 200, f"Expected 200, got {r1.status_code}"
    body1 = r1.json()
    assert "probability" in body1 and "model_version" in body1

    # Payload 2: Batch payload
    p2 = {"rows": [p1, {**p1, "temp_c": 92.0}]}
    r2 = requests.post(f"{base_url}/predict/batch", json=p2, timeout=10)
    print(f"Payload 2 (Batch): status={r2.status_code}, body={r2.text}")
    assert r2.status_code == 200, f"Expected 200, got {r2.status_code}"
    body2 = r2.json()
    assert len(body2["probabilities"]) == 2

    # Payload 3: Invalid payload (out-of-bounds load_pct) -> Expect 422 Unprocessable Entity
    p3 = {**p1, "load_pct": 250.0}
    r3 = requests.post(f"{base_url}/predict", json=p3, timeout=10)
    print(f"Payload 3 (Out of bounds): status={r3.status_code}, body={r3.text}")
    assert r3.status_code == 422, f"Expected 422, got {r3.status_code}"

    print("\nPASS  All 3 smoke test payloads behaved as expected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
