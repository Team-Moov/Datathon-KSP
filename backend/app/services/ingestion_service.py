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

from app.core.nlp import get_nlp_provider
from app.core.ocr import get_ocr_provider
from app.models.document import Document
from app.models.enums import DocumentFormat, ExtractionMethod, SourceType
from app.services.extraction.classifier import DocumentClassifier
from app.services.extraction.extractors import get_extractor
from app.services.entity_resolution import EntityResolutionService
from app.services.embedding_service import EmbeddingService
from app.services.graph_sync_service import GraphSyncService
from app.models.case import CaseMaster
from app.repositories.case_repository import CaseRepository
from app.repositories.person_repository import PersonRepository

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
        self.person_repo = PersonRepository(db)

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

        # ── Step 4a-financial: load transaction rows + sync account graph ─────
        if source_type == SourceType.FINANCIAL:
            await self._load_financial_data(extracted, doc)

        # ── Step 3.5: OCR fallback — scanned images/PDFs have no extractable text ──
        narrative_text = extracted.get("narrative_text") or extracted.get("brief_facts", "")
        if not narrative_text and file_format in (DocumentFormat.JPG, DocumentFormat.PNG, DocumentFormat.PDF):
            try:
                ocr = await get_ocr_provider().extract_text(file_path.read_bytes(), original_filename)
                if ocr.get("text"):
                    narrative_text = ocr["text"]
                    extracted["narrative_text"] = narrative_text
                    log.info("OCR text extracted", provider=ocr.get("provider"), chars=len(narrative_text))
            except Exception as exc:  # noqa: BLE001 — OCR is best-effort, never fail ingestion
                log.warning("OCR failed", error=str(exc))

        # ── Step 4: NER on the narrative (entities held for entity resolution) ──
        if narrative_text:
            try:
                extracted["entities"] = await get_nlp_provider().extract_entities(narrative_text)
                log.info("NER extracted", count=len(extracted["entities"]))
            except Exception as exc:  # noqa: BLE001 — NER is best-effort
                log.warning("NER failed", error=str(exc))

        # ── Step 4b: embed narrative text into vector store ───────────────────
        if narrative_text:
            await self.embedding_svc.embed_and_store(
                text=narrative_text,
                document_id=doc.id,
                incident_id=extracted.get("incident_id"),
                chunk_type=source_type,
                db=self.db,
            )

        # ── Step 4c: sync relationships to graph store ────────────────────────
        # Extraction never yields unit_id (it is a registration fact, not
        # something in the document text), so read it off the case. The graph
        # needs it: the multi-jurisdiction query, and the repeat-offender
        # early-warning detector built on it, group incidents by unit_id.
        case_id = extracted.get("case_id")
        if case_id and not extracted.get("unit_id"):
            case_row = await self.db.get(CaseMaster, uuid.UUID(str(case_id)))
            if case_row is not None:
                extracted["unit_id"] = case_row.unit_id
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

    async def _load_financial_data(self, extracted: Dict[str, Any], doc: Document) -> None:
        """
        Writes FinancialCsvExtractor's normalized rows into `financial_transaction`
        and syncs the Account-level graph, so an uploaded bank statement actually
        reaches FinancialCrimeService's detectors instead of stopping at the
        parsed-but-unused 'dataframe' the old CSV fallback produced.
        """
        from app.models.financial import FinancialTransaction

        raw_transactions = extracted.get("transactions", [])
        if not raw_transactions:
            log.warning(
                "Financial upload had no parseable transaction rows",
                document_id=str(doc.id),
                error=extracted.get("extraction_error"),
            )
            return

        name_to_person_id: Dict[str, uuid.UUID] = {}
        created_rows = []

        for raw in raw_transactions:
            linked_person_id = None

            given_id = raw.get("linked_person_id")
            if given_id:
                try:
                    candidate = uuid.UUID(str(given_id))
                    if await self.person_repo.get_by_id(candidate) is not None:
                        linked_person_id = candidate
                except ValueError:
                    pass

            if linked_person_id is None:
                name = raw.get("linked_person_name")
                if name:
                    if name not in name_to_person_id:
                        person = await self.entity_resolver.resolve_person_by_name(name, doc.id)
                        name_to_person_id[name] = person.id
                    linked_person_id = name_to_person_id[name]

            txn = FinancialTransaction(
                from_account=raw["from_account"],
                to_account=raw["to_account"],
                amount=raw["amount"],
                currency=raw.get("currency", "INR"),
                transaction_date=raw["transaction_date"],
                transaction_type=raw.get("transaction_type"),
                linked_person_id=linked_person_id,
                linked_incident_id=extracted.get("case_id"),
                # Model defaults is_synthetic=True (built for the seed script) —
                # these are real uploaded rows, must not be tagged as synthetic.
                is_synthetic=False,
            )
            self.db.add(txn)
            created_rows.append(txn)

        await self.db.flush()
        for row in created_rows:
            await self.db.refresh(row)

        await self.graph_sync.sync_financial_transactions([
            {
                "id": row.id,
                "from_account": row.from_account,
                "to_account": row.to_account,
                "amount": float(row.amount),
                "transaction_date": row.transaction_date,
                "linked_person_id": row.linked_person_id,
            }
            for row in created_rows
        ])

        log.info(
            "Financial transactions loaded",
            document_id=str(doc.id),
            count=len(created_rows),
            rows_skipped=extracted.get("rows_skipped", 0),
        )
