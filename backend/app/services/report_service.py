"""
Case report PDF generation + secure sharing (§ Enterprise Security & Governance
— Secure Report Sharing). Every field pulled into the report is a real column
from an already-existing model — CaseMaster header fields, the CaseStageEvent
timeline (§8.3), linked Document provenance (§3.1/§11), the latest RiskScore
including its shap_decomposition (§7.4/§11 — never just the bare score), and
investigator-support leads (§8.1, each already carrying source_tool/confidence).

Reports are built as HTML and rendered to PDF by the configured PdfRenderer
(local xhtml2pdf, or Catalyst SmartBrowz) — swap via settings.PDF_PROVIDER.
"""

import html
import io
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from pypdf import PdfReader, PdfWriter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.pdf import get_pdf_renderer
from app.core.security import hash_password
from app.models.case import CaseMaster
from app.models.document import Document
from app.models.offender import CriminalHistory, RiskScore
from app.models.person import PersonCaseRole
from app.models.reports import ReportShareLink
from app.models.user import User


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


# ── HTML templating ───────────────────────────────────────────────────────────

_STYLE = """
  @page { size: A4; margin: 2cm; }
  body { font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; font-size: 11px; }
  h1 { font-size: 18px; margin: 0 0 4px 0; }
  h2 { font-size: 13px; border-bottom: 1px solid #888; padding-bottom: 2px; margin: 16px 0 6px 0; }
  .meta { color: #555; font-size: 10px; margin-bottom: 8px; }
  .row { margin: 2px 0; }
  .sub { color: #444; padding-left: 14px; }
  .watermark { position: fixed; top: 45%; left: 12%; transform: rotate(-30deg);
               color: #cfcfcf; font-size: 20px; font-weight: bold; }
  .role { font-weight: bold; margin-top: 8px; }
  .msg { white-space: pre-wrap; padding-left: 12px; }
"""


def _doc(title: str, watermark: str, body: str) -> str:
    return (
        f"<html><head><meta charset='utf-8'><style>{_STYLE}</style></head><body>"
        f"<div class='watermark'>{html.escape(watermark)}</div>"
        f"<h1>{html.escape(title)}</h1>"
        f"<div class='meta'>{html.escape(watermark)}</div>"
        f"{body}</body></html>"
    )


def _confidential_watermark(issued_to: User) -> str:
    return (
        f"CONFIDENTIAL — issued to {issued_to.full_name} — "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}"
    )


def _case_report_html(
    case: CaseMaster,
    documents: List[Document],
    risk_scores: List[RiskScore],
    leads: Optional[List[Dict[str, Any]]],
    watermark: str,
) -> str:
    parts: List[str] = []
    disposition = case.chargesheet.cs_type.value if case.chargesheet else "Undetected/pending"
    parts.append(
        f"<div class='row'>District ID: {case.district_id or '-'} &nbsp;&nbsp; "
        f"Reported: {case.date_reported or '-'}</div>"
        f"<div class='row'>Disposition: {html.escape(str(disposition))}</div>"
    )

    parts.append("<h2>Timeline</h2>")
    for event in sorted(case.stage_events, key=lambda e: e.event_date):
        parts.append(
            f"<div class='row'>{event.event_date} — {html.escape(event.stage.value)} "
            f"(confidence {event.confidence:.2f})</div>"
        )

    parts.append("<h2>Evidence (Document Provenance)</h2>")
    for doc in documents:
        parts.append(
            f"<div class='row'>{html.escape(doc.original_filename)} — "
            f"{html.escape(doc.source_type.value)} via {html.escape(doc.extraction_method.value)}, "
            f"confidence {doc.confidence_score:.2f}</div>"
        )

    if risk_scores:
        parts.append("<h2>Risk Assessment</h2>")
        for score in risk_scores[:5]:
            parts.append(
                f"<div class='row'>Score {score.score:.2f} (model {html.escape(score.model_version)}, "
                f"human_reviewed={score.human_reviewed})</div>"
            )
            for feature, contribution in (score.shap_decomposition or {}).items():
                parts.append(f"<div class='sub'>{html.escape(str(feature))}: {contribution}</div>")

    if leads:
        parts.append("<h2>Investigative Leads</h2>")
        for lead in leads:
            parts.append(
                f"<div class='row'>{html.escape(str(lead.get('type', 'lead')))}: "
                f"{html.escape(str(lead.get('name', lead.get('person_id', '-'))))} "
                f"(source: {html.escape(str(lead.get('source_tool', '-')))}, "
                f"confidence {lead.get('confidence', '-')})</div>"
            )

    return _doc(f"Case Report — {case.crime_no}", watermark, "".join(parts))


def _chat_report_html(messages: List[Dict[str, str]], session_id: str, watermark: str) -> str:
    parts: List[str] = ["<h2>Transcript</h2>"]
    for msg in messages:
        content = msg.get("content", "").strip()
        if not content:
            continue
        role = "Investigator" if msg["role"] == "user" else "AI Assistant"
        parts.append(f"<div class='role'>{role}:</div>")
        parts.append(f"<div class='msg'>{html.escape(content)}</div>")
    return _doc(f"Conversation Transcript — {session_id}", watermark, "".join(parts))


# ── PDF builders ──────────────────────────────────────────────────────────────

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
    watermark = _confidential_watermark(issued_to)
    doc_html = _case_report_html(case, documents, risk_scores, leads, watermark)
    return await get_pdf_renderer().render_html(doc_html)


async def build_chat_report_pdf(
    messages: List[Dict[str, str]],
    session_id: str,
    issued_to: User,
) -> bytes:
    watermark = _confidential_watermark(issued_to)
    doc_html = _chat_report_html(messages, session_id, watermark)
    return await get_pdf_renderer().render_html(doc_html)


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
