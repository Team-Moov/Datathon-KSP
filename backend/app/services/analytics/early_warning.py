"""
Early-Warning detection service (capability #8 — Crime Forecasting & Early Warning).

Closes the one capability the platform names but never delivered: proactive alerts
for "repeat crimes, gang activity, or organized crime." Every alert is produced by
an existing deterministic detector — never an LLM — so it carries a source tool and
an evidence trail, exactly like the risk/link/MO derived-data tables.

Detectors (both parameter-free graph queries that the endpoint sweep already
proved green):
  - REPEAT_OFFENDER  ← NetworkAnalysisService.get_multi_jurisdiction_offenders()
                       (a person whose cases span multiple police jurisdictions —
                       the §3.3 organized/mobile-activity signal)
  - ORGANIZED_GROUP  ← NetworkAnalysisService.detect_communities()
                       (a dense co-offending community — a probable cell)

Idempotent: each candidate carries a deterministic `signature`; a re-scan inserts
only signatures not already present, so beat can run hourly without piling up
duplicates. EMERGING_HOTSPOT (Hawkes) and FINANCIAL (STR) are modelled by
AlertType and slot in here later without touching the model, endpoints, or UI.
"""

import hashlib
from typing import Any, Dict, List

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.alert import Alert
from app.models.enums import AlertSeverity, AlertStatus, AlertType
from app.services.analytics.network_analysis import NetworkAnalysisService

log = structlog.get_logger(__name__)

# Below these, a finding is too weak to be worth an investigator's attention.
_MIN_JURISDICTIONS = 2
_MIN_COMMUNITY_SIZE = 5


def _members_hash(person_ids: List[str]) -> str:
    """Stable fingerprint of a group's membership — independent of Louvain's
    arbitrary community-id labelling, which can differ run to run, so the same
    cell doesn't re-alert under a new id."""
    joined = ",".join(sorted(str(pid) for pid in person_ids))
    return hashlib.sha1(joined.encode()).hexdigest()[:16]


class EarlyWarningService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.network = NetworkAnalysisService()

    async def scan(self) -> Dict[str, Any]:
        """Run every detector, persist genuinely new alerts, return a summary."""
        candidates: List[Alert] = []
        candidates.extend(await self._scan_repeat_offenders())
        candidates.extend(await self._scan_organized_groups())

        inserted = await self._persist_new(candidates)
        log.info("early-warning scan complete", candidates=len(candidates), inserted=inserted)
        return {"candidates": len(candidates), "inserted": inserted}

    async def _scan_repeat_offenders(self) -> List[Alert]:
        offenders = await self.network.get_multi_jurisdiction_offenders()
        alerts: List[Alert] = []
        for row in offenders:
            count = int(row.get("jurisdiction_count", 0))
            if count < _MIN_JURISDICTIONS:
                continue
            person_id = row.get("person_id")
            name = row.get("name") or "Unknown person"
            severity = AlertSeverity.HIGH if count >= 4 else AlertSeverity.MEDIUM if count == 3 else AlertSeverity.LOW
            alerts.append(
                Alert(
                    alert_type=AlertType.REPEAT_OFFENDER,
                    severity=severity,
                    title=f"Repeat offender across {count} jurisdictions: {name}",
                    description=(
                        f"{name} appears as accused in cases spanning {count} distinct police "
                        f"jurisdictions — a signal of organized or mobile criminal activity."
                    ),
                    evidence={
                        "source_tool": "get_multi_jurisdiction_offenders",
                        "person_id": str(person_id),
                        "name": name,
                        "jurisdiction_count": count,
                        "units": row.get("units"),
                    },
                    source_tool="get_multi_jurisdiction_offenders",
                    confidence=min(1.0, 0.5 + 0.1 * count),
                    subject_person_id=self._as_uuid(person_id),
                    signature=f"repeat_offender:{person_id}:{count}",
                )
            )
        return alerts

    async def _scan_organized_groups(self) -> List[Alert]:
        assignments = await self.network.detect_communities()
        by_community: Dict[Any, List[str]] = {}
        for row in assignments:
            by_community.setdefault(row.get("community_id"), []).append(row.get("person_id"))

        alerts: List[Alert] = []
        for community_id, members in by_community.items():
            size = len(members)
            if size < _MIN_COMMUNITY_SIZE:
                continue
            severity = AlertSeverity.HIGH if size >= 10 else AlertSeverity.MEDIUM if size >= 7 else AlertSeverity.LOW
            alerts.append(
                Alert(
                    alert_type=AlertType.ORGANIZED_GROUP,
                    severity=severity,
                    title=f"Organized group: {size}-person co-offending cluster",
                    description=(
                        f"A community-detection pass found {size} people bound by shared "
                        f"co-offending — a probable organized cell worth reviewing together."
                    ),
                    evidence={
                        "source_tool": "detect_communities",
                        "community_id": community_id,
                        "member_count": size,
                        "member_person_ids": [str(m) for m in members],
                    },
                    source_tool="detect_communities",
                    confidence=min(1.0, 0.4 + 0.05 * size),
                    signature=f"organized_group:{_members_hash(members)}",
                )
            )
        return alerts

    async def _persist_new(self, candidates: List[Alert]) -> int:
        if not candidates:
            return 0
        signatures = [c.signature for c in candidates]
        existing = set(
            (await self.db.execute(select(Alert.signature).where(Alert.signature.in_(signatures)))).scalars().all()
        )
        # Also de-dup within this batch (two candidates can share a signature).
        seen_in_batch: set[str] = set()
        fresh: List[Alert] = []
        for candidate in candidates:
            if candidate.signature in existing or candidate.signature in seen_in_batch:
                continue
            seen_in_batch.add(candidate.signature)
            fresh.append(candidate)
        if fresh:
            self.db.add_all(fresh)
            await self.db.flush()
        return len(fresh)

    @staticmethod
    def _as_uuid(value: Any):
        import uuid

        try:
            return uuid.UUID(str(value))
        except (ValueError, TypeError, AttributeError):
            return None
