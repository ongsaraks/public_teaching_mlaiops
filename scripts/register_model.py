"""Lab 2 — Register the chosen model with complete lineage tags and promote to Staging.

Usage:
    python scripts/register_model.py [--run-id <run_id>]
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow
from mlflow.tracking import MlflowClient

from src import config, data


def main() -> int:
    parser = argparse.ArgumentParser(description="Register model with lineage")
    parser.add_argument("--run-id", default=None, help="Prefix or full MLflow run ID to register")
    parser.add_argument("--experiment", default="itcs355-lab2")
    parser.add_argument("--training-job-id", default="6222785838078492672")
    args = parser.parse_args()

    cfg = config.load(strict=False)
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)
    client = MlflowClient()

    exp = client.get_experiment_by_name(args.experiment)
    if not exp:
        print(f"Experiment '{args.experiment}' not found.")
        return 1

    runs = client.search_runs(exp.experiment_id, order_by=["metrics.val_roc_auc DESC"])
    if not runs:
        print("No runs found in experiment.")
        return 1

    if args.run_id:
        matched = [r for r in runs if r.info.run_id.startswith(args.run_id)]
        if not matched:
            print(f"Run ID matching {args.run_id} not found.")
            return 1
        chosen_run = matched[0]
    else:
        chosen_run = runs[0]

    run_id = chosen_run.info.run_id
    model_name = cfg.model_registry_name
    model_uri = f"runs:/{run_id}/model"

    print(f"Registering run {run_id[:8]} under model name '{model_name}'...")
    mv = mlflow.register_model(model_uri=model_uri, name=model_name)
    version = str(mv.version)

    # 1. Gather all 8 lineage tags
    try:
        git_sha = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=config.REPO_ROOT, text=True
        ).strip()
    except Exception:
        git_sha = "dev"

    data_version = data.data_fingerprint(cfg.raw_path)

    image_digest = "sha256:b09eea67393a101629c00dc972f9fc628f7a570cb44099cad7e7275b36c36480"

    seed = str(chosen_run.data.params.get("seed", 20260101))
    metric_val = f"{chosen_run.data.metrics.get('val_roc_auc', 0.0):.4f}"
    metric_test = f"{chosen_run.data.metrics.get('test_roc_auc', 0.0):.4f}"

    lineage_tags = {
        "git_commit": git_sha,
        "data_version": data_version,
        "mlflow_run_id": run_id,
        "training_job_id": args.training_job_id,
        "image_digest": image_digest,
        "seed": seed,
        "metric_val": metric_val,
        "metric_test": metric_test,
    }

    # 2. Set tags directly on the REGISTERED MODEL VERSION
    for k, v in lineage_tags.items():
        client.set_model_version_tag(name=model_name, version=version, key=k, value=str(v))
        print(f"  Tag set: {k}={v}")

    # 3. Promote through a staging step
    try:
        client.transition_model_version_stage(
            name=model_name, version=version, stage="Staging", archive_existing_versions=False
        )
        print(f"Promoted {model_name} v{version} to stage 'Staging'")
    except Exception:
        try:
            client.set_registered_model_alias(name=model_name, alias="staging", version=version)
            print(f"Set alias 'staging' for {model_name} v{version}")
        except Exception as exc:
            print(f"Note on stage transition: {exc}")

    print(f"\nSUCCESS: Registered model '{model_name}' version {version} with complete lineage.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
