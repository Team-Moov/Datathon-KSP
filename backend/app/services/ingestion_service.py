"""
Ingestion service — orchestrates the 5-step processing pipeline (§2.4):
1. Type/format classifier
2. Format-specific extraction
3. Entity resolution
4. Poly-store load
5. Audit log
"""

import uuid
from pathlib import Path
from typing import Any, Dict

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document
from app.models.enums import DocumentFormat, ExtractionMethod, SourceType
from app.services.extraction.classifier import DocumentClassifier
from app.services.extraction.extractors import get_extractor
from app.services.entity_resolution import EntityResolutionService
from app.services.embedding_service import EmbeddingService
from app.services.graph_sync_service import GraphSyncService
from app.repositories.case_repository import CaseRepository

log = structlog.get_logger(__name__)


class IngestionService:
    """
    Coordinates the full ingestion pipeline.
    Each step is independently replaceable — the service holds no extraction logic itself.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.classifier = DocumentClassifier()
        self.entity_resolver = EntityResolutionService(db)
        self.embedding_svc = EmbeddingService()
        self.graph_sync = GraphSyncService()
        self.case_repo = CaseRepository(db)

    async def ingest_file(
        self,
        file_path: Path,
        original_filename: str,
        raw_file_ref: str,
        user_id: uuid.UUID,
    ) -> Document:
        log.info("Ingestion started", filename=original_filename)

        # ── Step 1: classify ──────────────────────────────────────────────────
        source_type, file_format = await self.classifier.classify(file_path, original_filename)
        log.info("Document classified", source_type=source_type, format=file_format)

        # ── Step 2: extract ───────────────────────────────────────────────────
        extractor = get_extractor(source_type, file_format)
        extracted: Dict[str, Any] = await extractor.extract(file_path)
        extraction_method = extractor.method
        confidence = extracted.get("confidence", 1.0)

        # ── Provenance record (created before any data is written) ────────────
        doc = Document(
            source_type=source_type,
            file_format=file_format,
            original_filename=original_filename,
            raw_file_ref=raw_file_ref,
            extraction_method=extraction_method,
            confidence_score=confidence,
            staging_only=(source_type == SourceType.NEWS),
            ingested_by=user_id,
        )
        self.db.add(doc)
        await self.db.flush()
        await self.db.refresh(doc)

        # ── Step 3: entity resolution ─────────────────────────────────────────
        if not doc.staging_only:
            await self.entity_resolver.resolve(extracted, doc.id)

        # ── Step 4a: load case data ───────────────────────────────────────────
        if source_type in (SourceType.FIR, SourceType.CHARGESHEET, SourceType.JUDGMENT):
            await self._load_case_data(extracted, doc)

        # ── Step 4b: embed narrative text into vector store ───────────────────
        narrative_text = extracted.get("narrative_text") or extracted.get("brief_facts", "")
        if narrative_text:
            await self.embedding_svc.embed_and_store(
                text=narrative_text,
                document_id=doc.id,
                incident_id=extracted.get("incident_id"),
                chunk_type=source_type,
                db=self.db,
            )

        # ── Step 4c: sync relationships to graph store ────────────────────────
        await self.graph_sync.sync_document(extracted, doc)

        log.info("Ingestion complete", document_id=str(doc.id))
        return doc

    async def _load_case_data(self, extracted: Dict[str, Any], doc: Document) -> None:
        from app.models.case import CaseMaster, CaseStageEvent, ActSectionAssociation
        from app.models.enums import CaseStage
        import datetime

        crime_no = extracted.get("crime_no")
        if not crime_no:
            log.warning("No crime_no in extracted data — skipping case load", document_id=str(doc.id))
            return

        existing = await self.case_repo.get_by_crime_no(crime_no)
        if existing is None:
            case = CaseMaster(
                crime_no=crime_no,
                brief_facts=extracted.get("brief_facts"),
                source_type=doc.source_type,
                document_id=doc.id,
                date_reported=extracted.get("date_reported"),
                incident_from_date=extracted.get("incident_from_date"),
                incident_to_date=extracted.get("incident_to_date"),
                latitude=extracted.get("latitude"),
                longitude=extracted.get("longitude"),
            )
            self.db.add(case)
            await self.db.flush()
            await self.db.refresh(case)

            # Initial stage event
            self.db.add(
                CaseStageEvent(
                    case_id=case.id,
                    stage=CaseStage.REGISTERED,
                    event_date=extracted.get("date_reported") or datetime.date.today(),
                    source_document_id=doc.id,
                    confidence=doc.confidence_score,
                )
            )
            await self.db.flush()

        elif doc.source_type == SourceType.CHARGESHEET:
            # Update stage
            self.db.add(
                CaseStageEvent(
                    case_id=existing.id,
                    stage=CaseStage.CHARGESHEET_FILED,
                    event_date=extracted.get("cs_date") or datetime.date.today(),
                    source_document_id=doc.id,
                    confidence=doc.confidence_score,
                )
            )
            await self.db.flush()
