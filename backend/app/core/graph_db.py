"""
Neo4j async driver wrapper.
Exposes a singleton graph_db used across the application.
"""

import hashlib
import json
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import structlog
from neo4j import AsyncGraphDatabase

from app.core.cache import get_cache_provider
from app.core.config import settings

log = structlog.get_logger(__name__)


class GraphDatabase:
    """Thin async wrapper around Neo4j driver."""

    def __init__(self) -> None:
        self._driver = None

    async def connect(self) -> None:
        self._driver = AsyncGraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
            max_connection_pool_size=50,
        )
        await self._driver.verify_connectivity()
        log.info("Neo4j connection pool established", uri=settings.NEO4J_URI)

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    async def execute_query(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: str = "neo4j",
    ) -> List[Dict[str, Any]]:
        """Run a Cypher query and return a list of record dicts."""
        async with self._driver.session(database=database) as session:
            result = await session.run(query, parameters or {})
            return [dict(record) async for record in result]

    async def execute_write(
        self,
        query: str,
        parameters: Optional[Dict[str, Any]] = None,
        database: str = "neo4j",
    ) -> List[Dict[str, Any]]:
        """Run a write Cypher transaction."""
        async with self._driver.session(database=database) as session:
            result = await session.execute_write(
                lambda tx: tx.run(query, parameters or {})
            )
            return result

    async def run_in_transaction(self, tx_function, database: str = "neo4j"):
        """Execute a coroutine-based transaction function."""
        async with self._driver.session(database=database) as session:
            return await session.execute_write(tx_function)


# Module-level singleton — imported everywhere
graph_db = GraphDatabase()


# ── Graph query caching (§7a — performance layer, not a correctness change) ────
#
# Ego-network/community/link-prediction reads hit Neo4j on every call, and the
# network explorer page is exactly the kind of view a user re-opens or
# re-filters repeatedly. This caches a service method's JSON-serializable
# result verbatim in Redis (already provisioned for Celery) with a short TTL as
# a safety net, plus explicit invalidation on graph writes — see
# invalidate_graph_cache(), called from graph_sync_service.py after any
# node/edge mutation.

_CACHE_TTL_SECONDS = 60
_CACHE_NAMESPACE = "graph_cache"


def _build_cache_key(name: str, args: tuple, kwargs: dict) -> str:
    payload = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return f"{name}_{digest}"


def cached_graph_query(name: str, ttl_seconds: int = _CACHE_TTL_SECONDS) -> Callable:
    """
    Decorator for a read-only NetworkAnalysisService method. Caches the exact
    return value — including each predicted link's confidence/source_tool — so
    a cache hit is indistinguishable from a fresh read; this never changes what
    the underlying Cypher query would have returned, only how often it runs.

    Backed by the configured CacheProvider (Redis or Catalyst Cache) — swap via
    settings.CACHE_PROVIDER, no change here.
    """

    def decorator(fn: Callable) -> Callable:
        @wraps(fn)
        async def wrapper(self, *args, **kwargs):
            cache = get_cache_provider()
            key = _build_cache_key(name, args, kwargs)
            cached = await cache.get(_CACHE_NAMESPACE, key)
            if cached is not None:
                return json.loads(cached)

            result = await fn(self, *args, **kwargs)
            await cache.set(_CACHE_NAMESPACE, key, json.dumps(result, default=str), ttl_seconds)
            return result

        return wrapper

    return decorator


async def invalidate_graph_cache() -> None:
    """
    Invalidates every cached graph query in one O(1) namespace bump rather than
    tracking per-key dependencies — graph writes (new evidence landing) are
    infrequent relative to reads, so this guarantees no stale result survives a
    write, on either cache backend.
    """
    await get_cache_provider().invalidate_namespace(_CACHE_NAMESPACE)
