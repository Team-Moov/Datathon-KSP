"""
Provider-agnostic NER (ingestion step 4 — entities out of narrative text).

Gemini (Vertex AI, default) uses structured JSON extraction; Zia uses
Catalyst's text-analytics NER. Returns a normalized list of {text, type} either way.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class NlpProvider(ABC):
    @abstractmethod
    async def extract_entities(self, text: str) -> List[dict]:
        """Return [{'text': str, 'type': str}, ...]."""
