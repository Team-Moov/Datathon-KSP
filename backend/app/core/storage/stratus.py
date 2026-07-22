"""
Catalyst Stratus storage provider (REST-based).

Deliberately uses the Stratus REST API + an OAuth admin token rather than the
`zcatalyst-sdk` Python SDK: the SDK only self-authenticates when running *inside*
Catalyst (AppSail/Functions), whereas this REST client works both from local Docker
(with a refresh token) and on AppSail — one adapter, every environment.

Credentials (all from `.env`, see config.py):
  CATALYST_DC             data-center slug — "in" for this account (accounts.zoho.in)
  CATALYST_PROJECT_ID     numeric project id (Project-Rainfall = 54726000000013024)
  CATALYST_CLIENT_ID      Self Client id      (api-console.zoho.in)
  CATALYST_CLIENT_SECRET  Self Client secret
  CATALYST_REFRESH_TOKEN  refresh token minted with the Stratus scopes
  STRATUS_BUCKET          target bucket name

Refs are `stratus://<key>` so they are self-describing alongside `local://`/`seed://`.
"""

from __future__ import annotations

from typing import Optional

import httpx
import structlog

from app.core.catalyst_auth import catalyst_auth_header
from app.core.config import settings
from app.core.storage.base import StorageProvider

log = structlog.get_logger(__name__)


class StratusStorageProvider(StorageProvider):
    SCHEME = "stratus://"

    def __init__(self, bucket: str, project_id: str) -> None:
        if not bucket or not project_id:
            raise RuntimeError("STRATUS_BUCKET and CATALYST_PROJECT_ID are required for Stratus storage")
        self.bucket = bucket
        self.project_id = project_id
        dc = getattr(settings, "CATALYST_DC", "in")
        # Stratus serves each bucket on its own domain, e.g.
        #   https://crime-development.zohostratus.in   (development env)
        # Objects are addressed directly under it (S3-style), so STRATUS_BASE_URL is
        # that bucket URL. Falls back to the documented <bucket>-development pattern.
        self.base_url = (
            getattr(settings, "STRATUS_BASE_URL", "").rstrip("/")
            or f"https://{bucket}-development.zohostratus.{dc}"
        )

    def _key(self, ref: str) -> str:
        return ref[len(self.SCHEME):] if ref.startswith(self.SCHEME) else ref

    def _object_url(self, key: str) -> str:
        # S3-style: object addressed directly under the bucket domain.
        return f"{self.base_url}/{key.lstrip('/')}"

    async def _headers(self) -> dict:
        return await catalyst_auth_header()

    async def put(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        headers = await self._headers()
        headers["Content-Type"] = content_type or "application/octet-stream"
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.put(
                self._object_url(key),
                content=content,
                headers=headers,
            )
            resp.raise_for_status()
        log.info("Stratus put", bucket=self.bucket, key=key, bytes=len(content))
        return f"{self.SCHEME}{key}"

    async def get(self, ref: str) -> bytes:
        key = self._key(ref)
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.get(
                self._object_url(key), headers=await self._headers()
            )
            resp.raise_for_status()
            return resp.content

    async def delete(self, ref: str) -> None:
        key = self._key(ref)
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.delete(
                self._object_url(key), headers=await self._headers()
            )
            if resp.status_code not in (200, 204, 404):
                resp.raise_for_status()

    # local_path() falls back to base.StorageProvider — downloads to a temp file
    # via get(), which is exactly right for a remote backend.
