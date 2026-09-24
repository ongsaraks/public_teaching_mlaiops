"""GCP adapter. Implement upload/download/push_image for Lab 1.

SDK:  pip install google-cloud-storage google-cloud-aiplatform
Docs: storage.Client for GCS; Artifact Registry push goes through `docker push` after
      `gcloud auth configure-docker <region>-docker.pkg.dev`.

Hints for Lab 1:
  * BLOB_URI looks like gs://bucket/prefix — parse it here, never in src/.
  * Artifact Registry paths are region-scoped:
        <region>-docker.pkg.dev/<project>/<repo>/<image>
    A common first failure is pushing to gcr.io out of habit; it is a different service.
  * push_image must return the digest reference, not the tag.
  * GCP calls them labels, not tags, and they must be lowercase with no spaces.
    cfg.tags(1) already satisfies that constraint — do not "improve" the values.
"""
from __future__ import annotations

from typing import Any
import os
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse
from cloudlayer.base import CloudAdapter


class GcpAdapter(CloudAdapter):
    def upload(self, local_path: str, key: str) -> str:   
        parsed = urlparse(self.cfg.blob_uri)
        bucket_name = parsed.netloc
        prefix = parsed.path.strip("/")

        blob_name = f"{prefix}/{key}" if prefix else key

        # pyrefly: ignore [missing-import]
        from google.cloud import storage
        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.upload_from_filename(local_path)

        return f"gs://{bucket_name}/{blob_name}"
        # raise NotImplementedError("TODO Lab 1: blob.upload_from_filename, return the gs:// URI")

    def download(self, uri: str, local_path: str) -> None:
        parsed = urlparse(uri)
        bucket_name = parsed.netloc
        blob_name = parsed.path.lstrip("/")

        Path(local_path).parent.mkdir(parents=True, exist_ok=True)

        try:
            # pyrefly: ignore [missing-import]
            from google.cloud import storage
            client = storage.Client(project=self.cfg.project_id)
            bucket = client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.download_to_filename(local_path)
        except (ImportError, ModuleNotFoundError):
            import json
            import urllib.parse
            import urllib.request

            # Inside GCP container without google-cloud-storage installed:
            # Fetch IAM auth token from GCP VM metadata server
            token_req = urllib.request.Request(
                "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token",
                headers={"Metadata-Flavor": "Google"},
            )
            token = json.loads(urllib.request.urlopen(token_req, timeout=5).read().decode())["access_token"]

            # Download object from GCS REST API
            encoded_blob = urllib.parse.quote(blob_name, safe="")
            url = f"https://storage.googleapis.com/storage/v1/b/{bucket_name}/o/{encoded_blob}?alt=media"
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(req, timeout=60) as resp, open(local_path, "wb") as f:
                f.write(resp.read())
        # raise NotImplementedError("TODO Lab 1: blob.download_to_filename, creating parents")

    def push_image(self, local_tag: str) -> str:

        """Tag local Docker image, authenticate GCP Docker helper, push to Artifact Registry,
        and return digest-pinned URI (repo@sha256:...)."""
        # Parse image name and tag from local_tag (e.g. itcs355-lab1:dev)
        if ":" in local_tag:
            image_name, tag = local_tag.split(":", 1)
        else:
            image_name, tag = local_tag, "latest"
        # Construct target Artifact Registry image URI
        # e.g., asia-southeast1-docker.pkg.dev/project/repo/image_name:tag
        remote_tag = f"{self.cfg.container_registry}/{image_name}:{tag}"
        # 1. Tag image for Artifact Registry
        subprocess.run(["docker", "tag", local_tag, remote_tag], check=True)
        # 2. Configure Docker authentication for GCP Artifact Registry
        domain = f"{self.cfg.region}-docker.pkg.dev"
        sdk_bin = str(Path.home() / "google-cloud-sdk" / "bin")
        if sdk_bin not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{sdk_bin}:{os.environ.get('PATH', '')}"

        gcloud_cmd = shutil.which("gcloud") or f"{sdk_bin}/gcloud"
        try:
            token = subprocess.run([gcloud_cmd, "auth", "print-access-token"], capture_output=True, text=True, check=True).stdout.strip()
            subprocess.run(["docker", "login", "-u", "oauth2accesstoken", "--password-stdin", f"https://{domain}"], input=token, text=True, check=True)
        except Exception:
            subprocess.run([gcloud_cmd, "auth", "configure-docker", domain, "--quiet"], check=True)
        # 3. Docker push to GCP Artifact Registry
        subprocess.run(["docker", "push", remote_tag], check=True)
        # 4. Get repo@sha256:<digest> reference
        out = subprocess.run(
            ["docker", "inspect", "--format={{index .RepoDigests 0}}", remote_tag],
            capture_output=True, text=True, check=True
        )
        digest_ref = out.stdout.strip()
        if not digest_ref:
            raise RuntimeError(f"Could not retrieve image digest for {remote_tag}")
        
        return digest_ref

    def submit_training(self, image_uri: str, args: dict[str, Any]) -> str:
        """Submit a custom training job to Vertex AI using a custom container.
        Returns the job resource name / ID."""
        # pyrefly: ignore [missing-import]
        from google.cloud import aiplatform

        parsed_bucket = urlparse(self.cfg.blob_uri).netloc
        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
            staging_bucket=f"gs://{parsed_bucket}",
        )

        # Convert dictionary args to CLI flags
        cmd_args = []
        for k, v in args.items():
            flag = k.replace("_", "-")
            if isinstance(v, bool):
                if v:
                    cmd_args.append(f"--{flag}")
            else:
                cmd_args.extend([f"--{flag}", str(v)])

        # Use identity_ref if it is a GCP service account (*.gserviceaccount.com), otherwise let Vertex AI use default
        sa = self.cfg.identity_ref if self.cfg.identity_ref.endswith(".gserviceaccount.com") else None

        job = aiplatform.CustomJob(
            display_name=f"itcs355-train-{self.cfg.project_id}",
            worker_pool_specs=[{
                "machine_spec": {
                    "machine_type": "e2-standard-4",
                },
                "replica_count": 1,
                "container_spec": {
                    "image_uri": image_uri,
                    "args": cmd_args,
                    "env": [
                        {"name": "CLOUD_PROVIDER", "value": self.cfg.provider},
                        {"name": "PROJECT_ID", "value": self.cfg.project_id},
                        {"name": "REGION", "value": self.cfg.region},
                        {"name": "BLOB_URI", "value": self.cfg.blob_uri},
                        {"name": "MLFLOW_TRACKING_URI", "value": "sqlite:////tmp/mlflow.db"},
                    ],
                },
            }],
            labels=self.cfg.tags(2),
        )

        job.submit(service_account=sa)
        return job.resource_name


    def wait_training(self, job_id: str) -> dict[str, Any]:
        """Wait for the custom training job to complete and return status."""
        import time
        # pyrefly: ignore [missing-import]
        from google.cloud import aiplatform

        terminal_states = {
            "JOB_STATE_SUCCEEDED",
            "JOB_STATE_FAILED",
            "JOB_STATE_CANCELLED",
            "JOB_STATE_EXPIRED",
        }

        while True:
            job = aiplatform.CustomJob.get(job_id)
            status = job.state.name
            if status in terminal_states:
                break
            print(f"Waiting for training job {job_id.split('/')[-1]}... current status: {status}")
            time.sleep(15)

        return {
            "status": status,
            "error": job.error.message if job.error else None,
        }

        
        
        # raise NotImplementedError("TODO Lab 1: configure-docker, push, return repo@sha256:...")

    def register_model(self, model_uri: str, name: str) -> str:
        """Register model in MLflow Model Registry and return version string."""
        import mlflow
        from mlflow.tracking import MlflowClient

        mlflow.set_tracking_uri(self.cfg.mlflow_tracking_uri)
        mv = mlflow.register_model(model_uri=model_uri, name=name)
        return str(mv.version)

    def deploy(self, model_ref: str, endpoint: str, instance: str) -> str:
        """Deploy a containerized model to a Vertex AI Endpoint."""
        # pyrefly: ignore [missing-import]
        from google.cloud import aiplatform

        aiplatform.init(
            project=self.cfg.project_id,
            location=self.cfg.region,
        )

        model_version = getattr(self.cfg, "model_version", "1")
        model = aiplatform.Model.upload(
            display_name=f"itcs355-{endpoint}",
            serving_container_image_uri=model_ref,
            serving_container_predict_route="/predict",
            serving_container_health_route="/ready",
            serving_container_ports=[8080],
            serving_container_environment_variables={
                "MODEL_REGISTRY_NAME": self.cfg.model_registry_name,
                "MODEL_VERSION": str(model_version),
                "MLFLOW_TRACKING_URI": self.cfg.mlflow_tracking_uri,
            },
            labels=self.cfg.tags(3),
        )

        endpoints = aiplatform.Endpoint.list(
            filter=f'display_name="{endpoint}"',
            project=self.cfg.project_id,
            location=self.cfg.region,
        )
        if endpoints:
            ep = endpoints[0]
        else:
            ep = aiplatform.Endpoint.create(
                display_name=endpoint,
                project=self.cfg.project_id,
                location=self.cfg.region,
                labels=self.cfg.tags(3),
            )

        model.deploy(
            endpoint=ep,
            deployed_model_display_name=f"dep-{endpoint}",
            machine_type=instance,
            min_replica_count=1,
            max_replica_count=1,
            traffic_percentage=100,
        )
        return ep.resource_name

    def invoke(self, endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Invoke a Vertex AI endpoint via raw_predict."""
        import json
        # pyrefly: ignore [missing-import]
        from google.cloud import aiplatform

        aiplatform.init(project=self.cfg.project_id, location=self.cfg.region)
        if not endpoint.isdigit() and not endpoint.startswith("projects/"):
            eps = aiplatform.Endpoint.list(
                filter=f'display_name="{endpoint}"',
                project=self.cfg.project_id,
                location=self.cfg.region,
            )
            ep = eps[0] if eps else aiplatform.Endpoint(endpoint_name=endpoint)
        else:
            ep = aiplatform.Endpoint(endpoint_name=endpoint)
        resp = ep.raw_predict(
            body=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return json.loads(resp.text)

    def teardown(self, tags: dict[str, str]) -> list[str]:
        """Delete every resource carrying these tags."""
        # pyrefly: ignore [missing-import]
        from google.cloud import aiplatform

        aiplatform.init(project=self.cfg.project_id, location=self.cfg.region)
        deleted = []
        try:
            endpoints = aiplatform.Endpoint.list(project=self.cfg.project_id, location=self.cfg.region)
            for ep in endpoints:
                course_tag = tags.get("course", "itcs355")
                match = (hasattr(ep, "labels") and ep.labels and ep.labels.get("course") == course_tag)
                if match or ep.display_name.startswith("itcs355"):
                    ep_name = ep.display_name
                    try:
                        ep.undeploy_all()
                        ep.delete(force=True)
                        deleted.append(f"endpoint:{ep_name}")
                    except Exception as exc:
                        print(f"Error deleting endpoint {ep_name}: {exc}")
        except Exception as exc:
            print(f"Error listing endpoints for teardown: {exc}")
        return deleted

    # emit_metric                       -> Lab 4 (Cloud Monitoring time series)
    # generate                          -> Lab 5 (managed LLM endpoint; read usageMetadata for tokens)
    # teardown                          -> Lab 5 (filter resources by label)
