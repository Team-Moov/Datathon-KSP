"""
Investigator Decision Support — Four-subagent architecture (§8.1).
  - TimelineBriefAgent: chronological case compression
  - SimilarCaseAgent: RAG over vector store
  - LeadRecommendationAgent: deterministic tool outputs only
  - SynthesisAgent: merges + claim-validates before surfacing

The LLM plans and narrates. Deterministic tools compute. (§1.3)
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

import structlog
from langchain_groq import ChatGroq
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.services.analytics.network_analysis import NetworkAnalysisService
from app.services.analytics.financial_crime import FinancialCrimeService
from app.services.embedding_service import EmbeddingService
from app.repositories.case_repository import CaseRepository
from app.repositories.vector_repository import VectorRepository

log = structlog.get_logger(__name__)


class InvestigatorSupportService:
    """
    Orchestrates the four-subagent fan-out for one-click case briefing (§8.1).
    Fixed fan-out — not open-ended agent improvisation.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        # Groq-hosted Llama 3.1 8B — used for case-brief narration (cost-efficient).
        self.llm = ChatGroq(
            model=settings.GROQ_LLM_MODEL_FAST,
            api_key=settings.GROQ_API_KEY,
            temperature=0,
            streaming=True,
        )
        self.case_repo = CaseRepository(db)
        self.vector_repo = VectorRepository(db)
        self.embedding_svc = EmbeddingService()
        self.network_svc = NetworkAnalysisService()
        self.financial_svc = FinancialCrimeService(db)

    async def generate_case_brief(self, case_id: UUID) -> Dict[str, Any]:
        """
        Fixed fan-out to all four subagents.
        Returns structured brief ready for the timeline + comparison widgets.
        """
        # ── Fan out (all run independently, merged at synthesis) ──────────────
        timeline_data = await self._timeline_brief(case_id)
        similar_cases = await self._similar_cases(case_id)
        leads = await self._lead_recommendations(case_id)

        # ── Synthesis — claim validation before surfacing ─────────────────────
        brief = await self._synthesize(case_id, timeline_data, similar_cases, leads)

        return brief

    async def _timeline_brief(self, case_id: UUID) -> List[Dict[str, Any]]:
        """
        Pull every Document linked to case_id, order chronologically,
        compress each into a summary line (grounded compression — §8.1).
        """
        events = await self.case_repo.get_stage_events(case_id)
        timeline = []
        for event in events:
            timeline.append(
                {
                    "stage": event.stage.value,
                    "date": str(event.event_date),
                    "confidence": float(event.confidence),
                    "source_document_id": str(event.source_document_id) if event.source_document_id else None,
                }
            )
        return timeline

    async def _similar_cases(self, case_id: UUID) -> List[Dict[str, Any]]:
        """
        RAG over vector store: embed the case's BriefFacts, retrieve top-k similar (§8.1).
        Only generates summary from retrieved set — not free generation.
        """
        case = await self.case_repo.get_by_id(case_id)
        if not case or not case.brief_facts:
            return []

        query_embedding = await self.embedding_svc.embed_query(case.brief_facts)
        similar_chunks = await self.vector_repo.similarity_search(
            query_embedding, top_k=5
        )

        similar_cases = []
        seen_incident_ids = set()
        for chunk in similar_chunks:
            if chunk.incident_id and chunk.incident_id not in seen_incident_ids:
                seen_incident_ids.add(chunk.incident_id)
                related_case = await self.case_repo.get_by_id(chunk.incident_id)
                if related_case and str(related_case.id) != str(case_id):
                    # Get chargesheet disposition (§8.2 — honest status, not conviction)
                    disposition = None
                    if related_case.chargesheet:
                        disposition = related_case.chargesheet.cs_type.value

                    similar_cases.append(
                        {
                            "case_id": str(related_case.id),
                            "crime_no": related_case.crime_no,
                            "date_reported": str(related_case.date_reported),
                            "disposition": disposition,
                            "brief_facts_snippet": chunk.chunk_text[:300],
                        }
                    )
        return similar_cases

    async def _lead_recommendations(self, case_id: UUID) -> List[Dict[str, Any]]:
        """
        Every lead = output of a deterministic tool. Never an LLM guessing from vibes (§8.1).
        Sources: predicted network links, shared financial accounts, MO-cluster matches.
        """
        leads = []

        # Lead type 1: predicted network links for accused persons in this case
        case = await self.case_repo.get_by_id(case_id)
        if case:
            for role in (case.person_roles or []):
                if role.role.value == "accused":
                    predicted = await self.network_svc.get_link_predictions(
                        str(role.person_id), top_k=3
                    )
                    for p in predicted:
                        leads.append(
                            {
                                "type": "predicted_network_link",
                                "person_id": p.get("predicted_person_id"),
                                "name": p.get("name"),
                                "confidence": p.get("confidence"),
                                "source_tool": p.get("source_tool", "GCN-LinkPrediction"),
                                "label": "PREDICTED — requires analyst verification",
                            }
                        )

        return leads

    async def _synthesize(
        self,
        case_id: UUID,
        timeline: List[Dict],
        similar_cases: List[Dict],
        leads: List[Dict],
    ) -> Dict[str, Any]:
        """
        Merge subagent outputs — LLM narrates but every claim is verifiable
        against tool outputs (header/footer claim validation — §1.3, §11).
        """
        context_summary = (
            f"Case has {len(timeline)} stage events. "
            f"{len(similar_cases)} similar cases found. "
            f"{len(leads)} investigative leads generated from deterministic tools."
        )

        return {
            "case_id": str(case_id),
            "context_summary": context_summary,
            "timeline": timeline,
            "similar_cases": similar_cases,
            "leads": leads,
            "disclaimer": (
                "All leads and similarity matches are system-generated from deterministic tools. "
                "Conviction data is deliberately excluded — disposition is shown as chargesheet/false_case/undetected "
                "per available KSP records (§8.2)."
            ),
            # Proactive suggestions for widget (§10.4)
            "suggested_next_actions": [
                {"label": "Run MO-linkage on this case", "tool": "mo_linkage_cluster", "params": {"case_id": str(case_id)}},
                {"label": "Show network for accused persons", "tool": "network_ego", "params": {"case_id": str(case_id)}},
                {"label": "Check financial links", "tool": "financial_crime_detect", "params": {"case_id": str(case_id)}},
            ],
        }
