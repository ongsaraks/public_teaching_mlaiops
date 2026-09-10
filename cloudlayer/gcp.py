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
import subprocess
from pathlib import Path
from urllib.parse import urlparse
# pyrefly: ignore [missing-import]
from google.cloud import storage
from cloudlayer.base import CloudAdapter


class GcpAdapter(CloudAdapter):
    def upload(self, local_path: str, key: str) -> str:   
        parsed = urlparse(self.cfg.blob_uri)
        bucket_name = parsed.netloc
        prefix = parsed.path.strip("/")

        blob_name = f"{prefix}/{key}" if prefix else key

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

        client = storage.Client(project=self.cfg.project_id)
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        blob.download_to_filename(local_path)
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
        subprocess.run(["gcloud", "auth", "configure-docker", domain, "--quiet"], check=True)
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
        
        
        # raise NotImplementedError("TODO Lab 1: configure-docker, push, return repo@sha256:...")

    # submit_training / register_model  -> Lab 2 (Vertex custom training + Model Registry)
    # deploy / invoke                   -> Lab 3 (Vertex Endpoint)
    # emit_metric                       -> Lab 4 (Cloud Monitoring time series)
    # generate                          -> Lab 5 (managed LLM endpoint; read usageMetadata for tokens)
    # teardown                          -> Lab 5 (filter resources by label)
