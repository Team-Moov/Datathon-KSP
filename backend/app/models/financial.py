"""Financial transaction model (§9). Pure addition — not in real KSP schema."""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import FinancialAlertType


class FinancialTransaction(Base):
    """
    Typology-driven synthetic financial transactions (§9.1).
    Linked to Person and CaseMaster via FK — these are confirmed evidential links,
    not socio-economic correlation (see §9.4 integration note).
    """

    __tablename__ = "financial_transaction"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    from_account: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    to_account: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    transaction_type: Mapped[Optional[str]] = mapped_column(String(100))

    linked_person_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("person.id"), nullable=True, index=True
    )
    linked_incident_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        ForeignKey("case_master.id"), nullable=True
    )

    # Alert flags — set by the financial-crime detection service
    alert_type: Mapped[Optional[FinancialAlertType]] = mapped_column(Enum(FinancialAlertType))
    alert_confidence: Mapped[Optional[float]] = mapped_column(Float)
    alert_details: Mapped[Optional[dict]] = mapped_column(JSONB)
    """
    Structured STR-shaped output: typology detected, evidence trail, accounts involved.
    Shaped like a real Suspicious Transaction Report (§9.5) — NOT an invented format.
    """

    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=True)
    """Marks synthetically generated records — always distinguishable from real data."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
