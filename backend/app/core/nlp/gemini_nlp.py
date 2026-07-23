"""
Gemini (Vertex AI) NER provider — structured JSON extraction rather than a
dedicated NER model. Selected via NLP_PROVIDER=gemini.

Verified against live text (2026-07-23): Zia's text-analytics NER
(general_entities) has materially lower recall on Indian-name narrative text
than either local spaCy or this Gemini path — see zia_nlp.py's docstring
history. This is the default going forward; local/zia remain selectable.
"""

from __future__ import annotations

import json
from typing import List

import structlog
from google.genai import types

from app.core.config import settings
from app.core.nlp.base import NlpProvider
from app.core.vertex_ai_client import get_genai_client

log = structlog.get_logger(__name__)

_NER_PROMPT_PREFIX = """Extract every named entity from the text below. Return ONLY a JSON array of \
objects shaped {"text": "<exact substring>", "type": "<PERSON|LOCATION|ORGANIZATION>"} — no \
commentary, no markdown fences. "text" must be copied verbatim from the input, not paraphrased. \
If there are no entities, return [].

Text:
"""


class GeminiNlpProvider(NlpProvider):
    async def extract_entities(self, text: str) -> List[dict]:
        if not text or not text.strip():
            return []

        client = get_genai_client()
        response = await client.aio.models.generate_content(
            model=settings.GEMINI_MODEL_FAST,
            contents=[types.Content(role="user", parts=[types.Part(text=_NER_PROMPT_PREFIX + text)])],
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0),
        )
        try:
            parsed = json.loads(response.text)
        except (json.JSONDecodeError, TypeError):
            log.warning("Gemini NER returned non-JSON output", raw=response.text[:200] if response.text else None)
            return []

        if not isinstance(parsed, list):
            return []
        entities = [
            {"text": str(item["text"]), "type": str(item.get("type", "ENTITY"))}
            for item in parsed
            if isinstance(item, dict) and item.get("text")
        ]
        log.info("Gemini NER extracted", entities=len(entities))
        return entities
