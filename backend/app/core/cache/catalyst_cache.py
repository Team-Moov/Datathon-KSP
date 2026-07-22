"""
Catalyst Cache provider (REST-based), using the shared Catalyst OAuth token.

Notes vs. Redis:
- Catalyst Cache expiry is in **hours** (min 1, default 48), so the app's 60s
  "safety-net" TTL becomes 1 hour here. Correctness still holds: invalidation is
  explicit (version bump on graph writes), and the TTL is only a backstop.
- `cache_name` must be a simple token, so composite keys use `_` separators and
  hex digests (no `:`), which the namespace/version scheme already produces.

Segment: if CATALYST_CACHE_SEGMENT is unset, the project's default segment is
discovered once via the segments API.
"""

from __future__ import annotations

import hashlib
import math
from typing import Optional

import httpx
import structlog

from app.core.cache.base import CacheProvider
from app.core.catalyst_auth import catalyst_auth_header
from app.core.config import settings

log = structlog.get_logger(__name__)

_MAX_EXPIRY_HOURS = 48  # Catalyst Cache hard limit (expiry_in_hours must be 1..48)
_VERSION_TTL_SECONDS = _MAX_EXPIRY_HOURS * 3600  # version keys live as long as allowed


class CatalystCacheProvider(CacheProvider):
    def __init__(self, project_id: str, segment_id: str = "") -> None:
        if not project_id:
            raise RuntimeError("CATALYST_PROJECT_ID is required for Catalyst Cache")
        dc = getattr(settings, "CATALYST_DC", "in")
        self._api_base = getattr(settings, "CATALYST_API_BASE", "") or f"https://api.catalyst.zoho.{dc}"
        self._project_id = project_id
        self._segment_id = segment_id or ""

    async def _segment(self) -> str:
        if self._segment_id:
            return self._segment_id
        # Discover the default segment once.
        url = f"{self._api_base}/baas/v1/project/{self._project_id}/segment"
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(url, headers=await catalyst_auth_header())
            resp.raise_for_status()
            data = resp.json().get("data") or []
        if not data:
            raise RuntimeError("No Catalyst Cache segment found; create one or set CATALYST_CACHE_SEGMENT")
        self._segment_id = str(data[0]["id"])
        log.info("Catalyst Cache segment discovered", segment_id=self._segment_id)
        return self._segment_id

    async def _cache_url(self) -> str:
        seg = await self._segment()
        return f"{self._api_base}/baas/v1/project/{self._project_id}/segment/{seg}/cache"

    @staticmethod
    def _hours(ttl_seconds: int) -> int:
        # Catalyst Cache accepts expiry_in_hours in [1, 48].
        return min(_MAX_EXPIRY_HOURS, max(1, math.ceil(ttl_seconds / 3600)))

    @staticmethod
    def _safe_name(cache_name: str) -> str:
        # Catalyst caps cache_name length (~50 chars). Composite namespace/version/key
        # names can exceed that, so hash to a fixed 40-char digest — deterministic, so
        # reads and writes agree, and version bumps still change the digest.
        return hashlib.sha1(cache_name.encode("utf-8")).hexdigest()

    async def _get_raw(self, cache_name: str) -> Optional[str]:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                await self._cache_url(),
                params={"cacheKey": self._safe_name(cache_name)},
                headers=await catalyst_auth_header(),
            )
        if resp.status_code == 404:
            return None
        if resp.status_code != 200:
            return None
        payload = resp.json().get("data") or {}
        # A miss can come back as 200 with an empty/absent value.
        val = payload.get("cache_value")
        return val if val not in ("", None) else None

    async def _put_raw(self, cache_name: str, value: str, ttl_seconds: int) -> None:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                await self._cache_url(),
                json={
                    "cache_name": self._safe_name(cache_name),
                    "cache_value": value,
                    "expiry_in_hours": self._hours(ttl_seconds),
                },
                headers=await catalyst_auth_header(),
            )
            resp.raise_for_status()

    async def _version(self, namespace: str) -> str:
        return (await self._get_raw(f"ver_{namespace}")) or "0"

    async def get(self, namespace: str, key: str) -> Optional[str]:
        version = await self._version(namespace)
        return await self._get_raw(f"{namespace}_{version}_{key}")

    async def set(self, namespace: str, key: str, value: str, ttl_seconds: int) -> None:
        version = await self._version(namespace)
        await self._put_raw(f"{namespace}_{version}_{key}", value, ttl_seconds)

    async def invalidate_namespace(self, namespace: str) -> None:
        version = int(await self._version(namespace))
        await self._put_raw(f"ver_{namespace}", str(version + 1), _VERSION_TTL_SECONDS)
