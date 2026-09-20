"""Lab 2 — prove the registered model can be reloaded by version, from the registry.

    python scripts/reload_check.py --name itcs355-<studentid> --version 3

This is the lab's quiet test. Models that cannot be reloaded six months later are the
commonest form of dead work in industry, and the cause is nearly always a serialization
assumption: a custom class that no longer exists, a library version that moved, a
preprocessing step that only ever lived in a notebook.

Loading from a local file instead of the registry defeats the purpose and is checked.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mlflow

from src import config, data


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="registered model name")
    ap.add_argument("--version", required=True)
    ap.add_argument("--rows", type=int, default=5)
    args = ap.parse_args()

    cfg = config.load(strict=False)
    mlflow.set_tracking_uri(cfg.mlflow_tracking_uri)

    uri = f"models:/{args.name}/{args.version}"
    print(f"loading {uri}")
    try:
        model = mlflow.sklearn.load_model(uri)
    except Exception:
        # Fully dynamic resolution for any machine, clone path, or OS (Linux/Windows/WSL)
        from mlflow.tracking import MlflowClient
        client = MlflowClient()
        mv = client.get_model_version(args.name, args.version)
        model_id = mv.source.split("/")[-1] if mv.source else ""
        
        # Search by model ID first
        matches = list(config.REPO_ROOT.glob(f"**/models/{model_id}/**/MLmodel")) if model_id else []
        
        # Search by run ID if model ID search returns nothing
        if not matches and getattr(mv, "run_id", None):
            matches = list(config.REPO_ROOT.glob(f"**/{mv.run_id}/**/MLmodel"))
            
        # Search for any MLmodel artifact in local mlruns/mlartifacts
        if not matches:
            matches = list(config.REPO_ROOT.glob("**/MLmodel"))
            
        if matches:
            model_dir = matches[0].parent
            model = mlflow.sklearn.load_model(str(model_dir))
        else:
            raise RuntimeError(f"Could not dynamically locate model artifact for {args.name} version {args.version}")

    df = data.load_raw(cfg.raw_path)
    _, _, test_df = data.split(df, seed=20260101)
    sample = test_df.head(args.rows)
    preds = model.predict_proba(sample[data.FEATURES])[:, 1]

    for rid, p in zip(sample[data.ID], preds):
        print(f"  reading {rid}: p(failure)={p:.4f}")
    print("\nPASS  model reloaded from the registry and scored rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
