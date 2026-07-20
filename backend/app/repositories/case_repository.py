"""Case repository — queries against CaseMaster and related tables."""

from datetime import date
from typing import List, Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.case import CaseMaster, CaseStageEvent
from app.models.enums import Role
from app.models.user import User
from app.repositories.base import BaseRepository

# Ranks tied to a single posting (§ RBAC district-wise permissions) only see cases
# in their own district. Command tier and the two specialist tracks (whose job is
# inherently cross-district analysis/oversight) are unrestricted.
_DISTRICT_UNRESTRICTED_ROLES = frozenset(
    {Role.DSP, Role.SP, Role.DGP, Role.CRIME_ANALYST, Role.POLICY_MAKER}
)


class CaseRepository(BaseRepository[CaseMaster]):
    def __init__(self, db: AsyncSession) -> None:
        super().__init__(CaseMaster, db)

    @staticmethod
    def scope_to_user(stmt, user: Optional[User]):
        """
        District-wise data isolation. A district-less user holding a restricted
        rank sees nothing rather than everything — `district_id == None` binds to
        SQL `= NULL`, which is never true, so this fails safe by construction.
        """
        if user is None or user.role in _DISTRICT_UNRESTRICTED_ROLES:
            return stmt
        return stmt.where(CaseMaster.district_id == user.district_id)

    async def get_by_crime_no(self, crime_no: str, user: Optional[User] = None) -> Optional[CaseMaster]:
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
        stmt = self.scope_to_user(stmt, user)
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
        user: Optional[User] = None,
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
        stmt = self.scope_to_user(stmt, user)
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
