"""Case repository — queries against CaseMaster and related tables."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import CaseMaster, CaseStageEvent
from app.repositories.base import BaseRepository


class CaseRepository(BaseRepository[CaseMaster]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(CaseMaster, db)

    async def get_by_crime_no(self, crime_no: str) -> Optional[CaseMaster]:
        stmt = (
            select(CaseMaster)
            .where(CaseMaster.crime_no == crime_no)
            .options(
                selectinload(CaseMaster.act_section_associations),
                selectinload(CaseMaster.chargesheet),
                selectinload(CaseMaster.stage_events),
                selectinload(CaseMaster.person_roles),
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def search_by_date_range(
        self,
        start: date,
        end: date,
        district_id: Optional[int] = None,
        crime_head_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> List[CaseMaster]:
        filters = [
            CaseMaster.date_reported >= start,
            CaseMaster.date_reported <= end,
        ]
        if district_id:
            filters.append(CaseMaster.district_id == district_id)
        if crime_head_id:
            filters.append(CaseMaster.crime_head_id == crime_head_id)

        stmt = select(CaseMaster).where(and_(*filters)).offset(skip).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_cases_by_person(self, person_id: UUID) -> List[CaseMaster]:
        """All cases where this person has any role."""
        from app.models.person import PersonCaseRole

        stmt = (
            select(CaseMaster)
            .join(PersonCaseRole, PersonCaseRole.case_id == CaseMaster.id)
            .where(PersonCaseRole.person_id == person_id)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_stage_events(self, case_id: UUID) -> List[CaseStageEvent]:
        stmt = (
            select(CaseStageEvent)
            .where(CaseStageEvent.case_id == case_id)
            .order_by(CaseStageEvent.event_date.asc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def add_stage_event(self, event: CaseStageEvent) -> CaseStageEvent:
        self.db.add(event)
        await self.db.flush()
        await self.db.refresh(event)
        return event
