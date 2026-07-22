"""
Catalyst Zia NER provider (REST). POST {api_base}/baas/v1/project/{id}/ml/text-analytics/ner
with JSON {"document": [text]}. Scope ZohoCatalyst.mlkit.READ (same token as Zia OCR).

Zia's response shape is normalized best-effort into [{text, type}]; the exact shape
is confirmed on the first live call, so parsing stays tolerant of key variations.
"""

from __future__ import annotations

from typing import List

import httpx
import structlog

from app.core.catalyst_auth import catalyst_auth_header
from app.core.config import settings
from app.core.nlp.base import NlpProvider

log = structlog.get_logger(__name__)


def _normalize(data) -> List[dict]:
    """Flatten Zia's NER response into [{text, type}] tolerantly."""
    out: List[dict] = []

    def _emit(token, tag):
        if token:
            out.append({"text": str(token), "type": str(tag) if tag else "ENTITY"})

    def _walk(node):
        if isinstance(node, dict):
            token = node.get("token") or node.get("word") or node.get("text") or node.get("entity")
            tag = node.get("ner_tag") or node.get("tag") or node.get("type") or node.get("label")
            if token:
                _emit(token, tag)
            else:
                for v in node.values():
                    _walk(v)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(data)
    return out


class ZiaNlpProvider(NlpProvider):
    def __init__(self, project_id: str) -> None:
        if not project_id:
            raise RuntimeError("CATALYST_PROJECT_ID is required for Zia NER")
        dc = getattr(settings, "CATALYST_DC", "in")
        api_base = getattr(settings, "CATALYST_API_BASE", "") or f"https://api.catalyst.zoho.{dc}"
        self.endpoint = f"{api_base}/baas/v1/project/{project_id}/ml/text-analytics/ner"

    async def extract_entities(self, text: str) -> List[dict]:
        if not text or not text.strip():
            return []
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                self.endpoint, headers=await catalyst_auth_header(), json={"document": [text]}
            )
            resp.raise_for_status()
            data = resp.json().get("data")
        entities = _normalize(data)
        log.info("Zia NER extracted", entities=len(entities))
        return entities
