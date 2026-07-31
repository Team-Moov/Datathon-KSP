"""
Cache-provider factory. Select via `settings.CACHE_PROVIDER`:
  - "redis"    → RedisCacheProvider — default
  - "catalyst" → CatalystCacheProvider (Catalyst Cache, added once provisioned)

Call sites use `get_cache_provider()` and never import a concrete provider.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.cache.base import CacheProvider
from app.core.config import settings

__all__ = ["CacheProvider", "get_cache_provider"]


@lru_cache(maxsize=1)
def get_cache_provider() -> CacheProvider:
    provider = getattr(settings, "CACHE_PROVIDER", "redis")

    if provider == "redis":
        from app.core.cache.redis_cache import RedisCacheProvider

        return RedisCacheProvider(settings.REDIS_URL)

    if provider == "catalyst":
        from app.core.cache.catalyst_cache import CatalystCacheProvider

        return CatalystCacheProvider(
            project_id=settings.CATALYST_PROJECT_ID,
            segment_id=settings.CATALYST_CACHE_SEGMENT,
        )

    raise ValueError(f"Unknown CACHE_PROVIDER: {provider!r}")
