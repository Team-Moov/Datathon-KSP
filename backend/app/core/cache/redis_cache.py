"""Redis-backed cache provider — the default, and the current behaviour."""

from __future__ import annotations

from typing import Optional

import redis.asyncio as aioredis

from app.core.cache.base import CacheProvider


class RedisCacheProvider(CacheProvider):
    def __init__(self, url: str) -> None:
        self._redis = aioredis.from_url(url, decode_responses=True)

    async def _version(self, namespace: str) -> str:
        v = await self._redis.get(f"__ver__:{namespace}")
        return v or "0"

    def _key(self, namespace: str, version: str, key: str) -> str:
        return f"{namespace}:v{version}:{key}"

    async def get(self, namespace: str, key: str) -> Optional[str]:
        version = await self._version(namespace)
        return await self._redis.get(self._key(namespace, version, key))

    async def set(self, namespace: str, key: str, value: str, ttl_seconds: int) -> None:
        version = await self._version(namespace)
        await self._redis.set(self._key(namespace, version, key), value, ex=ttl_seconds)

    async def invalidate_namespace(self, namespace: str) -> None:
        # Bump the version — existing v<n> keys become unreachable and TTL out.
        await self._redis.incr(f"__ver__:{namespace}")
