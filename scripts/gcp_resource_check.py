"""Check active GCP Vertex AI resources to prevent unexpected billing."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import config

try:
    from google.cloud import aiplatform
except ImportError:
    print("google.cloud.aiplatform not installed in this environment.")
    sys.exit(0)


def main():
    cfg = config.load(strict=False)
    print(f"Project: {cfg.project_id} | Region: {cfg.region}")
    aiplatform.init(project=cfg.project_id, location=cfg.region)

    print("\n[1] Checking Vertex AI Endpoints (BILLABLE HOURLY):")
    try:
        endpoints = aiplatform.Endpoint.list(project=cfg.project_id, location=cfg.region)
        if not endpoints:
            print("  -> None found (0 active endpoints). You are not being billed for idle endpoints.")
        else:
            print(f"  -> WARNING: {len(endpoints)} active endpoint(s) found:")
            for ep in endpoints:
                models = ep.list_models()
                print(f"     Name: {ep.display_name} | Resource: {ep.resource_name} | Deployed models: {len(models)}")
    except Exception as e:
        print(f"  -> Error checking endpoints: {e}")

    print("\n[2] Checking Vertex AI Custom Training Jobs:")
    try:
        jobs = aiplatform.CustomJob.list(project=cfg.project_id, location=cfg.region)
        running = [j for j in jobs if j.state.name == "JOB_STATE_RUNNING"]
        if not running:
            print(f"  -> 0 running training jobs ({len(jobs)} total historical jobs).")
        else:
            print(f"  -> WARNING: {len(running)} training job(s) currently RUNNING:")
            for j in running:
                print(f"     Job: {j.display_name} | State: {j.state.name}")
    except Exception as e:
        print(f"  -> Error checking custom jobs: {e}")


if __name__ == "__main__":
    main()
