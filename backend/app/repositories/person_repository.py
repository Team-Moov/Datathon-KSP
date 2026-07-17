"""Person repository with entity-resolution helpers."""

from typing import List, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.person import Person, PersonCaseRole
from app.repositories.base import BaseRepository


class PersonRepository(BaseRepository[Person]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(Person, db)

    async def search_by_name(self, query: str, limit: int = 20) -> List[Person]:
        """Simple ILIKE name search — used as a pre-step for entity resolution."""
        stmt = (
            select(Person)
            .where(Person.full_name.ilike(f"%{query}%"))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def find_by_alias(self, alias: str) -> List[Person]:
        """Find persons whose aliases array contains the given alias."""
        from sqlalchemy import func as sqlfunc, cast
        from sqlalchemy.dialects.postgresql import ARRAY, TEXT

        stmt = select(Person).where(
            Person.aliases.any(alias)  # PostgreSQL ARRAY @> operator via any()
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_with_history(self, person_id: UUID) -> Optional[Person]:
        stmt = (
            select(Person)
            .where(Person.id == person_id)
            .options(
                selectinload(Person.case_roles).selectinload(PersonCaseRole.case),
                selectinload(Person.criminal_history),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_case_roles(self, person_id: UUID) -> List[PersonCaseRole]:
        stmt = (
            select(PersonCaseRole)
            .where(PersonCaseRole.person_id == person_id)
            .options(selectinload(PersonCaseRole.case))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())
