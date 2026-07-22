"""
Provider-agnostic cache interface.

Namespace-based rather than flat keys, because invalidation must work on backends
that can't scan-by-prefix (Catalyst Cache is plain key-value). `invalidate_namespace`
is implemented via a per-namespace version counter: bumping it makes every existing
entry unreachable, and the entries then expire by their own TTL. Redis could use
SCAN+DELETE, but the version scheme keeps both backends identical and O(1).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class CacheProvider(ABC):
    """Short-TTL cache keyed by (namespace, key). Values are strings (JSON)."""

    @abstractmethod
    async def get(self, namespace: str, key: str) -> Optional[str]:
        ...

    @abstractmethod
    async def set(self, namespace: str, key: str, value: str, ttl_seconds: int) -> None:
        ...

    @abstractmethod
    async def invalidate_namespace(self, namespace: str) -> None:
        """Invalidate every entry in a namespace (bumps its version counter)."""
