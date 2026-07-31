"""
Entity Resolution Service — Step 3 of the ingestion pipeline (§2.4, §3.3).
The single hardest and most valuable step: merging the same accused person appearing
across multiple FIRs under different aliases/addresses into one Person node.
All derived entity merges are held for human verification before touching a risk score.
"""

import uuid
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.person import Person, PersonCaseRole
from app.models.enums import PersonRole
from app.repositories.person_repository import PersonRepository

log = structlog.get_logger(__name__)

# Confidence threshold above which a candidate is considered the same person
MATCH_THRESHOLD = 0.85


class EntityResolutionService:
    """
    Resolves named entities from extracted document data to canonical Person records.
    Uses name similarity + alias matching as the primary signal.
    All merges set human_verified=False until explicitly reviewed.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.person_repo = PersonRepository(db)

    async def resolve(self, extracted: Dict[str, Any], document_id: uuid.UUID) -> None:
        """
        Resolve all persons mentioned in the extracted payload.
        Creates new Person records or links to existing ones.
        """
        persons_raw = extracted.get("persons", [])
        case_id = extracted.get("case_id")

        for person_data in persons_raw:
            person = await self._resolve_person(person_data, document_id)
            if case_id and person_data.get("role"):
                await self._link_person_to_case(person, case_id, person_data)

    async def resolve_person_by_name(self, full_name: str, document_id: uuid.UUID) -> Person:
        """Public single-name entry point for callers that only have a name,
        not a full extracted person_data dict — e.g. financial-transaction
        ingestion resolving a 'linked_person_name' CSV column. Reuses the same
        fuzzy-match-or-create logic as document entity resolution."""
        return await self._resolve_person({"full_name": full_name}, document_id)

    async def _resolve_person(
        self, person_data: Dict[str, Any], document_id: uuid.UUID
    ) -> Person:
        name = person_data.get("full_name", "").strip()
        if not name:
            return await self._create_person(person_data, document_id)

        # 1. Exact name match
        candidates = await self.person_repo.search_by_name(name, limit=10)

        # 2. Alias match
        for alias in person_data.get("aliases", []):
            alias_matches = await self.person_repo.find_by_alias(alias)
            candidates.extend(alias_matches)

        # 3. Similarity scoring
        best_match: Optional[Person] = None
        best_score = 0.0
        for candidate in candidates:
            score = self._name_similarity(name, candidate.full_name)
            # Boost score if addresses or aliases overlap
            if self._aliases_overlap(
                person_data.get("aliases", []), candidate.aliases or []
            ):
                score = min(1.0, score + 0.1)
            if score > best_score:
                best_score = score
                best_match = candidate

        if best_match and best_score >= MATCH_THRESHOLD:
            log.info(
                "Entity resolved to existing person",
                name=name,
                person_id=str(best_match.id),
                score=best_score,
            )
            # Merge any new aliases
            await self._merge_aliases(best_match, person_data.get("aliases", []))
            return best_match

        # No match — create new (human_verified=False)
        return await self._create_person(person_data, document_id)

    async def _create_person(
        self, person_data: Dict[str, Any], document_id: uuid.UUID
    ) -> Person:
        person = Person(
            full_name=person_data.get("full_name", "Unknown"),
            aliases=person_data.get("aliases", []),
            date_of_birth=person_data.get("date_of_birth"),
            sex=person_data.get("sex"),
            nationality=person_data.get("nationality"),
            permanent_address=person_data.get("permanent_address"),
            present_address=person_data.get("present_address"),
            source_document_id=document_id,
            human_verified=False,
        )
        self.db.add(person)
        await self.db.flush()
        await self.db.refresh(person)
        log.info("New person entity created", person_id=str(person.id), name=person.full_name)
        return person

    async def _link_person_to_case(
        self, person: Person, case_id: uuid.UUID, person_data: Dict[str, Any]
    ) -> None:
        role_str = person_data.get("role", "accused").lower()
        try:
            role = PersonRole(role_str)
        except ValueError:
            role = PersonRole.ACCUSED

        link = PersonCaseRole(
            person_id=person.id,
            case_id=case_id,
            role=role,
            arrested=person_data.get("arrested", False),
            arrest_date=person_data.get("arrest_date"),
        )
        self.db.add(link)
        await self.db.flush()

    async def _merge_aliases(self, person: Person, new_aliases: List[str]) -> None:
        existing = set(person.aliases or [])
        merged = list(existing | set(new_aliases))
        if merged != list(existing):
            person.aliases = merged
            await self.db.flush()

    @staticmethod
    def _name_similarity(a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    @staticmethod
    def _aliases_overlap(a_aliases: List[str], b_aliases: List[str]) -> bool:
        return bool(set(a.lower() for a in a_aliases) & set(b.lower() for b in b_aliases))
