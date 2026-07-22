"""Document ingestion endpoint — multipart file upload."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.config import settings
from app.core.database import get_db
from app.core.permissions import Permission, require_permission
from app.core.storage import get_storage_provider
from app.models.user import User
from app.services.ingestion_service import IngestionService

router = APIRouter()
MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


class DocumentOut(BaseModel):
    id: uuid.UUID
    source_type: str
    file_format: str
    original_filename: str
    confidence_score: float
    staging_only: bool

    model_config = {"from_attributes": True}


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.UPLOAD_DOCUMENT)),
):
    """
    Accepts any supported document format and runs the full ingestion pipeline.
    News files land in staging_only=True and require analyst promotion.
    """
    # Size check
    content = await file.read()
    if len(content) > MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )

    # Store via the configured provider (local filesystem / Catalyst Stratus / GCS).
    storage = get_storage_provider()
    upload_id = uuid.uuid4()
    suffix = Path(file.filename).suffix
    key = f"documents/{upload_id}{suffix}"
    raw_ref = await storage.put(key, content, file.content_type)

    svc = IngestionService(db)
    # Extractors need a filesystem path; the provider yields one (real path for
    # local, temp download for remote backends) for the duration of ingestion.
    async with storage.local_path(raw_ref, suffix=suffix) as dest:
        doc = await svc.ingest_file(
            file_path=dest,
            original_filename=file.filename,
            raw_file_ref=raw_ref,
            user_id=current_user.id,
        )
    await log_audit_event(
        db, action="document.uploaded", resource_type="document", resource_id=str(doc.id),
        payload={"original_filename": file.filename, "staging_only": doc.staging_only},
    )
    return DocumentOut.model_validate(doc)


@router.post("/{document_id}/promote", status_code=status.HTTP_200_OK)
async def promote_staged_document(
    document_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PROMOTE_DOCUMENT)),
):
    """
    Analyst explicitly promotes a staged news document to verified status.
    Required by the news-staging rule (§2.2) — no auto-merge.
    """
    from app.models.document import Document
    from sqlalchemy import select

    stmt = select(Document).where(Document.id == document_id)
    result = await db.execute(stmt)
    doc = result.scalar_one_or_none()
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.staging_only:
        raise HTTPException(status_code=400, detail="Document is not in staging")

    doc.staging_only = False
    doc.human_verified = True
    await db.flush()
    await log_audit_event(db, action="document.promoted", resource_type="document", resource_id=str(document_id))
    return {"status": "promoted", "document_id": str(document_id)}
