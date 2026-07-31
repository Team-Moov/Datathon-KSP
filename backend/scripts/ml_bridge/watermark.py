from datetime import datetime
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def ensure_watermark_table(session: AsyncSession) -> None:
    await session.execute(text("""
        CREATE TABLE IF NOT EXISTS ml_sync_watermark (
            sync_name TEXT PRIMARY KEY,
            last_computed_at TIMESTAMP NOT NULL
        )
    """))


async def get_watermark(session: AsyncSession, sync_name: str) -> Optional[datetime]:
    result = await session.execute(
        text("SELECT last_computed_at FROM ml_sync_watermark WHERE sync_name = :name"),
        {"name": sync_name},
    )
    row = result.first()
    return row[0] if row else None


async def set_watermark(session: AsyncSession, sync_name: str, last_computed_at: datetime) -> None:
    await session.execute(text("""
        INSERT INTO ml_sync_watermark (sync_name, last_computed_at)
        VALUES (:name, :ts)
        ON CONFLICT (sync_name) DO UPDATE SET last_computed_at = EXCLUDED.last_computed_at
    """), {"name": sync_name, "ts": last_computed_at})