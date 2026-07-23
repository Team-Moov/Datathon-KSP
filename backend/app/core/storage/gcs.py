"""
Google Cloud Storage provider.

Uses the official `google-cloud-storage` client, authenticated via Application
Default Credentials (a service-account JSON pointed to by
`GOOGLE_APPLICATION_CREDENTIALS`, or the ambient identity when running on GCP
compute). The client library's own transport already runs blocking calls in a
thread pool when used from `asyncio.to_thread`, so this adapter offloads each
call explicitly rather than pulling in a separate async GCS client.

Refs are `gcs://<key>` so they are self-describing alongside `local://`/
`stratus://`/`seed://`.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import structlog

from app.core.config import settings
from app.core.storage.base import StorageProvider

log = structlog.get_logger(__name__)


class GCSStorageProvider(StorageProvider):
    SCHEME = "gcs://"

    def __init__(self, bucket: str, project_id: str) -> None:
        if not bucket:
            raise RuntimeError("GCS_BUCKET is required for GCS storage")
        from google.cloud import storage  # lazy import — only required when selected

        self.bucket_name = bucket
        self._client = storage.Client(project=project_id or None)
        self._bucket = self._client.bucket(bucket)

    def _key(self, ref: str) -> str:
        return ref[len(self.SCHEME):] if ref.startswith(self.SCHEME) else ref

    async def put(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        blob = self._bucket.blob(key)
        await asyncio.to_thread(
            blob.upload_from_string, content, content_type=content_type or "application/octet-stream"
        )
        log.info("GCS put", bucket=self.bucket_name, key=key, bytes=len(content))
        return f"{self.SCHEME}{key}"

    async def get(self, ref: str) -> bytes:
        blob = self._bucket.blob(self._key(ref))
        return await asyncio.to_thread(blob.download_as_bytes)

    async def delete(self, ref: str) -> None:
        blob = self._bucket.blob(self._key(ref))
        try:
            await asyncio.to_thread(blob.delete)
        except Exception as exc:
            # No error if it's already gone — matches the other providers' delete() contract.
            from google.api_core.exceptions import NotFound

            if not isinstance(exc, NotFound):
                raise

    # local_path() falls back to base.StorageProvider — downloads to a temp file
    # via get(), which is exactly right for a remote backend.
