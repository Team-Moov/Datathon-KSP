"""
Immutable change history — automatic field-level diff on direct user edits
(§ Enterprise Security & Governance — Immutable Change History).

Deliberately narrow: TRACKED_MODELS covers only the handful of models a person
edits through the UI (CaseMaster, Person, PersonCaseRole, User). It excludes
RiskScore/MOLinkageCluster/predicted-link tables (insert-only by design, §7.4/§11
of the design doc — already versioned their own way) and CaseStageEvent/
FinancialTransaction (append-only ingestion/ledger tables, not user-edited records).

Registered globally on sqlalchemy.orm.Session — this is the documented way to use
ORM-level events under the asyncio extension, since AsyncSession delegates flush()
to an internal sync Session where these events actually fire.
"""

from typing import Any, Optional

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

from app.core.request_context import current_user_id_ctx
from app.models.audit import RecordChangeHistory
from app.models.case import CaseMaster
from app.models.person import Person, PersonCaseRole
from app.models.user import User

TRACKED_MODELS = (CaseMaster, Person, PersonCaseRole, User)

# Bookkeeping columns, or columns that shouldn't be echoed back in plain text —
# not something a "change history" viewer needs to show.
_IGNORED_FIELDS = {"id", "created_at", "updated_at", "version", "last_login", "hashed_password"}


def _stringify(value: Any) -> Optional[str]:
    return None if value is None else str(value)


@event.listens_for(Session, "before_flush")
def _record_field_changes(session: Session, flush_context, instances) -> None:
    changed_by = current_user_id_ctx.get()

    for obj in session.dirty:
        if not isinstance(obj, TRACKED_MODELS):
            continue
        if not session.is_modified(obj, include_collections=False):
            continue

        state = inspect(obj)
        table_name = obj.__tablename__
        record_id = _stringify(getattr(obj, "id", None)) or ""

        for attr in state.mapper.column_attrs:
            if attr.key in _IGNORED_FIELDS:
                continue

            history = state.attrs[attr.key].history
            if not history.has_changes():
                continue

            old_value = _stringify(history.deleted[0]) if history.deleted else None
            new_value = _stringify(history.added[0]) if history.added else None
            if old_value == new_value:
                continue

            session.add(
                RecordChangeHistory(
                    table_name=table_name,
                    record_id=record_id,
                    field_name=attr.key,
                    old_value=old_value,
                    new_value=new_value,
                    changed_by=changed_by,
                )
            )
