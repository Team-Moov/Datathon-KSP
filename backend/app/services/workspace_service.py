"""
Investigator Workspace aggregation (§ Enterprise Security & Governance —
Investigator Workspace). Pulls together exactly the entities the design doc
already models for one case — CaseMaster, PersonCaseRole/Person, Document,
CaseStageEvent — plus the platform-only CaseNote, with masking applied per the
caller's permissions (app/core/masking.py). Nothing here computes anything new;
it's a read-shaped view over data every other endpoint already produces.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.masking import mask_person_display_name, mask_religion_caste
from app.core.permissions import Permission, role_has_permission
from app.models.case import CaseMaster
from app.models.document import Document
from app.models.enums import PersonRole
from app.models.person import PersonCaseRole
from app.models.user import User
from app.models.workspace import CaseNote
from app.repositories.case_repository import CaseRepository

_ROLE_LABELS = {
    PersonRole.ACCUSED: "Accused",
    PersonRole.VICTIM: "Victim",
    PersonRole.WITNESS: "Witness",
    PersonRole.COMPLAINANT: "Complainant",
}


async def _case_visible_to_user(db: AsyncSession, case_id: UUID, user: User) -> bool:
    stmt = CaseRepository.scope_to_user(select(CaseMaster.id).where(CaseMaster.id == case_id), user)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


async def build_case_workspace(
    db: AsyncSession, case_id: UUID, current_user: User
) -> Optional[Dict[str, Any]]:
    if not await _case_visible_to_user(db, case_id, current_user):
        return None

    stmt = (
        select(CaseMaster)
        .where(CaseMaster.id == case_id)
        .options(
            selectinload(CaseMaster.stage_events),
            selectinload(CaseMaster.chargesheet),
            selectinload(CaseMaster.person_roles).selectinload(PersonCaseRole.person),
        )
    )
    result = await db.execute(stmt)
    case = result.scalar_one_or_none()
    if case is None:
        return None

    has_pii = role_has_permission(current_user.role, Permission.VIEW_PII_UNMASKED)
    has_sensitive = role_has_permission(current_user.role, Permission.VIEW_CASE_SENSITIVE)

    people_by_role: Dict[str, List[Dict[str, Any]]] = {label: [] for label in _ROLE_LABELS.values()}
    ordinal_counters: Dict[str, int] = {}
    for role in case.person_roles:
        label = _ROLE_LABELS.get(role.role, "Other")
        ordinal_counters[label] = ordinal_counters.get(label, 0) + 1
        ordinal = chr(ord("A") + ((ordinal_counters[label] - 1) % 26))
        person = role.person
        people_by_role.setdefault(label, [])
        people_by_role[label].append(
            {
                "person_id": str(person.id),
                "name": mask_person_display_name(person.full_name, has_pii, label, ordinal),
                "human_verified": person.human_verified,
                "arrested": role.arrested,
                "bail_granted": role.bail_granted,
                "religion_id": mask_religion_caste(role.religion_id, has_pii),
                "caste_id": mask_religion_caste(role.caste_id, has_pii),
            }
        )

    documents_result = await db.execute(select(Document).where(Document.linked_incident_id == case_id))
    documents = [
        {
            "document_id": str(doc.id),
            "original_filename": doc.original_filename,
            "source_type": doc.source_type.value,
            "extraction_method": doc.extraction_method.value,
            "confidence_score": doc.confidence_score,
            "human_verified": doc.human_verified,
            "staging_only": doc.staging_only,
        }
        for doc in documents_result.scalars().all()
    ]

    notes_result = await db.execute(
        select(CaseNote).where(CaseNote.case_id == case_id).order_by(CaseNote.pinned.desc(), CaseNote.updated_at.desc())
    )
    notes = [serialize_note(n) for n in notes_result.scalars().all()]

    timeline = [
        {
            "stage": event.stage.value,
            "event_date": str(event.event_date),
            "confidence": float(event.confidence),
        }
        for event in sorted(case.stage_events, key=lambda e: e.event_date)
    ]

    return {
        "case": {
            "id": str(case.id),
            "crime_no": case.crime_no,
            "date_reported": str(case.date_reported) if case.date_reported else None,
            "district_id": case.district_id,
            "case_status_id": case.case_status_id,
            "brief_facts": case.brief_facts if has_sensitive else None,
            "disposition": case.chargesheet.cs_type.value if case.chargesheet else None,
            "version": case.version,
        },
        "people": people_by_role,
        "documents": documents,
        "timeline": timeline,
        "notes": notes,
    }


def serialize_note(note: CaseNote) -> Dict[str, Any]:
    return {
        "note_id": str(note.id),
        "author_id": str(note.author_id),
        "content": note.content,
        "pinned": note.pinned,
        "version": note.version,
        "updated_at": note.updated_at.isoformat(),
    }
