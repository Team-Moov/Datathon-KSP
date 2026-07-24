"""
Numbered, idempotent schema-upgrade steps — a lightweight stand-in for Alembic
until this schema stabilizes enough to adopt it properly (noted in the README).
`Base.metadata.create_all` (run just before this in init_db()) only ever adds
new tables/columns; it silently does nothing the moment an existing column needs
to change shape. Every step here is written to be safe to re-run (IF EXISTS /
IF NOT EXISTS guards), and schema_version.version is only bumped after a step
succeeds, so a step never applies twice — even across restarts or a crash
mid-upgrade.
"""

from typing import Awaitable, Callable, List, Tuple

import structlog
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

log = structlog.get_logger(__name__)


async def _step_0001_baseline(conn) -> None:
    """
    Placeholder baseline. Everything in this pass (RBAC/audit/MFA/masking/
    workspace/reports tables, CaseMaster.version, Person.version) is new and
    fully described by Base.metadata.create_all, so there's nothing to ALTER
    yet. The next breaking change (a rename, a type change, a NOT NULL backfill)
    gets its own numbered function appended below — never edit a step that has
    already shipped.
    """
    return


async def _step_0002_add_incident_time(conn) -> None:
    """
    CaseMaster never captured time-of-occurrence, only date — the real IIF-1
    FIR form has this field, but it was never modeled here, so hour-of-day
    crime analytics were never possible. Nullable, never backfilled: existing
    rows stay NULL, only newly-created/edited cases populate it going forward.
    """
    await conn.execute(
        text("ALTER TABLE case_master ADD COLUMN IF NOT EXISTS incident_time TIME")
    )


UPGRADE_STEPS: List[Tuple[int, Callable[..., Awaitable[None]]]] = [
    (1, _step_0001_baseline),
    (2, _step_0002_add_incident_time),
]


async def run_pending_upgrades(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_version (
                    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                    version INTEGER NOT NULL DEFAULT 0
                )
                """
            )
        )
        await conn.execute(
            text("INSERT INTO schema_version (id, version) VALUES (1, 0) ON CONFLICT (id) DO NOTHING")
        )
        result = await conn.execute(text("SELECT version FROM schema_version WHERE id = 1"))
        current_version = result.scalar_one()

    for step_version, step_fn in UPGRADE_STEPS:
        if step_version <= current_version:
            continue
        async with engine.begin() as conn:
            await step_fn(conn)
            await conn.execute(text("UPDATE schema_version SET version = :v WHERE id = 1"), {"v": step_version})
        log.info("Applied schema upgrade step", version=step_version)
