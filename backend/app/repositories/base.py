"""
Generic async repository base — CRUD helpers used by all concrete repositories.
"""

from typing import Any, Dict, Generic, List, Optional, Type, TypeVar
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, model: Type[ModelType], db: AsyncSession) -> None:
        self.model = model
        self.db = db

    async def get_by_id(self, id: Any) -> Optional[ModelType]:
        result = await self.db.get(self.model, id)
        return result

    async def get_all(self, skip: int = 0, limit: int = 100) -> List[ModelType]:
        stmt = select(self.model).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        stmt = select(func.count()).select_from(self.model)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def create(self, obj: ModelType) -> ModelType:
        self.db.add(obj)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update(self, obj: ModelType, data: Dict[str, Any]) -> ModelType:
        for key, value in data.items():
            setattr(obj, key, value)
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def update_with_version(
        self, id: Any, expected_version: int, data: Dict[str, Any]
    ) -> Optional[ModelType]:
        """
        Optimistic-concurrency update for models carrying a `version` column.
        `with_for_update` row-locks for the length of this transaction, so the
        read-check-write sequence can't race with a concurrent editor — they
        block until this transaction commits, then correctly see the bumped
        version and get None back. Returns None on a stale/missing row; the
        endpoint turns that into a 409 Conflict.
        """
        obj = await self.db.get(self.model, id, with_for_update=True)
        if obj is None or getattr(obj, "version", None) != expected_version:
            return None
        for key, value in data.items():
            setattr(obj, key, value)
        obj.version = expected_version + 1
        await self.db.flush()
        await self.db.refresh(obj)
        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.db.delete(obj)
        await self.db.flush()
