"""
Case report PDF generation + secure sharing (§ Enterprise Security & Governance
— Secure Report Sharing). Every field pulled into the report is a real column
from an already-existing model — CaseMaster header fields, the CaseStageEvent
timeline (§8.3), linked Document provenance (§3.1/§11), the latest RiskScore
including its shap_decomposition (§7.4/§11 — never just the bare score), and
investigator-support leads (§8.1, each already carrying source_tool/confidence).
"""

import io
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import hash_password
from app.models.case import CaseMaster
from app.models.document import Document
from app.models.offender import CriminalHistory, RiskScore
from app.models.person import PersonCaseRole
from app.models.reports import ReportShareLink
from app.models.user import User

_PAGE_BOTTOM_MARGIN = 4 * cm


async def _load_case_for_report(db: AsyncSession, case_id: UUID) -> Optional[CaseMaster]:
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
    return result.scalar_one_or_none()


async def _load_documents(db: AsyncSession, case_id: UUID) -> List[Document]:
    stmt = select(Document).where(Document.linked_incident_id == case_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _load_latest_risk_scores(db: AsyncSession, case: CaseMaster) -> List[RiskScore]:
    person_ids = [role.person_id for role in case.person_roles]
    if not person_ids:
        return []
    stmt = (
        select(RiskScore)
        .join(CriminalHistory, RiskScore.criminal_history_id == CriminalHistory.id)
        .where(CriminalHistory.person_id.in_(person_ids))
        .order_by(RiskScore.computed_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _draw_watermark(c: canvas.Canvas, watermark_text: str, width: float, height: float) -> None:
    c.saveState()
    c.setFont("Helvetica", 11)
    c.setFillGray(0.75, 0.5)
    c.translate(width / 2, height / 2)
    c.rotate(45)
    c.drawCentredString(0, 0, watermark_text)
    c.restoreState()


class _ReportCanvas:
    """Small stateful wrapper so each section doesn't repeat page-break bookkeeping."""

    def __init__(self, c: canvas.Canvas, width: float, height: float, watermark_text: str) -> None:
        self.c = c
        self.width = width
        self.height = height
        self.watermark_text = watermark_text
        self.y = height - 2 * cm

    def heading(self, text: str) -> None:
        self._ensure_space(1.2 * cm)
        self.c.setFont("Helvetica-Bold", 12)
        self.c.drawString(2 * cm, self.y, text)
        self.y -= 0.7 * cm
        self.c.setFont("Helvetica", 9)

    def line(self, text: str, indent: float = 2.2 * cm) -> None:
        self._ensure_space(0.5 * cm)
        self.c.drawString(indent, self.y, text[:110])
        self.y -= 0.48 * cm

    def _ensure_space(self, needed: float) -> None:
        if self.y - needed < _PAGE_BOTTOM_MARGIN:
            _draw_watermark(self.c, self.watermark_text, self.width, self.height)
            self.c.showPage()
            self.y = self.height - 2 * cm
            self.c.setFont("Helvetica", 9)

    def finish(self) -> None:
        _draw_watermark(self.c, self.watermark_text, self.width, self.height)
        self.c.showPage()


async def build_case_report_pdf(
    db: AsyncSession,
    case_id: UUID,
    issued_to: User,
    leads: Optional[List[Dict[str, Any]]] = None,
) -> bytes:
    case = await _load_case_for_report(db, case_id)
    if case is None:
        raise ValueError(f"Case {case_id} not found")

    documents = await _load_documents(db, case_id)
    risk_scores = await _load_latest_risk_scores(db, case)

    buffer = io.BytesIO()
    width, height = A4
    watermark_text = (
        f"CONFIDENTIAL — issued to {issued_to.full_name} — "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
    )
    report = _ReportCanvas(canvas.Canvas(buffer, pagesize=A4), width, height, watermark_text)

    report.c.setFont("Helvetica-Bold", 16)
    report.c.drawString(2 * cm, report.y, f"Case Report — {case.crime_no}")
    report.y -= 1 * cm
    report.c.setFont("Helvetica", 10)
    report.line(f"District ID: {case.district_id or '-'}    Reported: {case.date_reported or '-'}", indent=2 * cm)
    disposition = case.chargesheet.cs_type.value if case.chargesheet else "Undetected/pending"
    report.line(f"Disposition: {disposition}", indent=2 * cm)

    report.heading("Timeline")
    for event in sorted(case.stage_events, key=lambda e: e.event_date):
        report.line(f"{event.event_date} - {event.stage.value} (confidence {event.confidence:.2f})")

    report.heading("Evidence (Document Provenance)")
    for doc in documents:
        report.line(
            f"{doc.original_filename} - {doc.source_type.value} via "
            f"{doc.extraction_method.value}, confidence {doc.confidence_score:.2f}"
        )

    if risk_scores:
        report.heading("Risk Assessment")
        for score in risk_scores[:5]:
            report.line(
                f"Score {score.score:.2f} (model {score.model_version}, "
                f"human_reviewed={score.human_reviewed})"
            )
            for feature, contribution in (score.shap_decomposition or {}).items():
                report.line(f"- {feature}: {contribution}", indent=2.6 * cm)

    if leads:
        report.heading("Investigative Leads")
        for lead in leads:
            report.line(
                f"{lead.get('type', 'lead')}: {lead.get('name', lead.get('person_id', '-'))} "
                f"(source: {lead.get('source_tool', '-')}, confidence {lead.get('confidence', '-')})"
            )

    report.finish()
    report.c.save()
    buffer.seek(0)
    return buffer.getvalue()


def apply_password_protection(pdf_bytes: bytes, password: str) -> bytes:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    writer.encrypt(password)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


async def create_share_link(
    db: AsyncSession,
    case_id: UUID,
    created_by: User,
    password: Optional[str] = None,
    expires_in_hours: int = 72,
    max_downloads: int = 5,
) -> ReportShareLink:
    link = ReportShareLink(
        case_id=case_id,
        created_by=created_by.id,
        token=secrets.token_urlsafe(32),
        password_hash=hash_password(password) if password else None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=expires_in_hours),
        max_downloads=max_downloads,
    )
    db.add(link)
    await db.flush()
    await db.refresh(link)
    return link
