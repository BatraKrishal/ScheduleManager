from __future__ import annotations

import hashlib
import io
import logging
import os
import re
from datetime import timedelta
from typing import Optional

logger = logging.getLogger("minio_service")


class MinioStorageService:
    def __init__(self):
        self.endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
        self.access_key = os.getenv("MINIO_ACCESS_KEY", "minioadmin")
        self.secret_key = os.getenv("MINIO_SECRET_KEY", "minioadmin")
        self.bucket = os.getenv("MINIO_BUCKET", "sih-artifacts")
        self.secure = os.getenv("MINIO_SECURE", "false").lower() == "true"
        self.fallback_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".artifacts_storage",
        )
        self._client = None
        self._minio_available: Optional[bool] = None

    def _get_client(self):
        if self._client is None:
            try:
                import urllib3
                from minio import Minio
                # Use zero-retry, fast 100ms connect timeout so offline probe never hangs tests
                http_client = urllib3.PoolManager(
                    timeout=urllib3.util.Timeout(connect=0.1, read=0.3),
                    retries=urllib3.util.Retry(total=0, connect=0, read=0),
                )
                client = Minio(
                    self.endpoint,
                    access_key=self.access_key,
                    secret_key=self.secret_key,
                    secure=self.secure,
                    http_client=http_client,
                )
                self._client = client
            except Exception as e:
                logger.warning(f"Failed to initialize MinIO client: {e}")
                self._client = None
        return self._client

    def is_minio_connected(self) -> bool:
        if self._minio_available is not None:
            return self._minio_available
        client = self._get_client()
        if not client:
            self._minio_available = False
            return False
        try:
            # Ping by checking bucket exists
            client.bucket_exists(self.bucket)
            self._minio_available = True
            return True
        except Exception as e:
            logger.info(f"MinIO server not reachable at {self.endpoint} ({e}). Using persistent local fallback.")
            self._minio_available = False
            return False

    def ensure_bucket_exists(self) -> None:
        """Create bucket if it does not exist."""
        if self.is_minio_connected():
            client = self._get_client()
            if not client.bucket_exists(self.bucket):
                client.make_bucket(self.bucket)
                logger.info(f"Created MinIO bucket: {self.bucket}")
        else:
            os.makedirs(os.path.join(self.fallback_dir, self.bucket), exist_ok=True)

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename to prevent path traversal and unsafe characters."""
        base = os.path.basename(filename)
        sanitized = re.sub(r"[^\w\.\-\_]", "_", base)
        return sanitized or "unnamed_artifact"

    @staticmethod
    def compute_sha256(data: bytes) -> str:
        """Compute SHA-256 hex digest of file bytes."""
        return hashlib.sha256(data).hexdigest()

    def generate_object_key(
        self, project_id: str, report_id: str, artifact_id: str, original_filename: str
    ) -> str:
        """
        Deterministic MinIO object-key convention:
        projects/{project_id}/reports/{report_id}/artifacts/{artifact_id}/{sanitized_filename}
        """
        clean_name = self.sanitize_filename(original_filename)
        return f"projects/{project_id}/reports/{report_id}/artifacts/{artifact_id}/{clean_name}"

    def upload_artifact(self, object_key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """
        Upload binary data to MinIO, or fallback storage if MinIO is offline.
        Returns the object key.
        """
        self.ensure_bucket_exists()
        if self.is_minio_connected():
            client = self._get_client()
            stream = io.BytesIO(data)
            client.put_object(
                bucket_name=self.bucket,
                object_name=object_key,
                data=stream,
                length=len(data),
                content_type=content_type,
            )
            logger.info(f"Uploaded {len(data)} bytes to MinIO at {self.bucket}/{object_key}")
        else:
            # Fallback storage
            full_path = os.path.join(self.fallback_dir, self.bucket, object_key)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "wb") as f:
                f.write(data)
            logger.info(f"Saved {len(data)} bytes to local fallback at {full_path}")
        return object_key

    def get_artifact_bytes(self, object_key: str) -> bytes:
        """
        Retrieve binary data from MinIO or fallback storage.
        """
        if self.is_minio_connected():
            client = self._get_client()
            response = None
            try:
                response = client.get_object(self.bucket, object_key)
                return response.read()
            finally:
                if response:
                    response.close()
                    response.release_conn()
        else:
            full_path = os.path.join(self.fallback_dir, self.bucket, object_key)
            if not os.path.exists(full_path):
                raise FileNotFoundError(f"Artifact object not found at {object_key}")
            with open(full_path, "rb") as f:
                return f.read()

    def get_presigned_view_url(self, object_key: str, expires_seconds: int = 900) -> str:
        """
        Generate a temporary presigned URL for viewing/downloading the artifact.
        """
        if self.is_minio_connected():
            client = self._get_client()
            return client.presigned_get_object(
                bucket_name=self.bucket,
                object_name=object_key,
                expires=timedelta(seconds=expires_seconds),
            )
        else:
            # Return direct API route for local viewing
            return f"/api/v1/artifacts/download?key={object_key}"


# Global singleton instance
minio_service = MinioStorageService()
