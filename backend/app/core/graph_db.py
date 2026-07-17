"""
Neo4j async driver wrapper.
Exposes a singleton graph_db used across the application.
"""

from typing import Any, Dict, List, Optional

import structlog
from neo4j import AsyncGraphDatabase

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
