"""Location model — geocoordinates linked to case incidents."""

import uuid
from typing import Optional

from sqlalchemy import ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Location(Base):
    __tablename__ = "location"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    incident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("case_master.id"), nullable=False, index=True)

    latitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    longitude: Mapped[Optional[float]] = mapped_column(Numeric(10, 7))
    address_text: Mapped[Optional[str]] = mapped_column(Text)
    place_type: Mapped[Optional[str]] = mapped_column(String(100))
    """e.g. residential, commercial, public_road"""
    jurisdiction_unit_id: Mapped[Optional[int]] = mapped_column(ForeignKey("unit.id"))
