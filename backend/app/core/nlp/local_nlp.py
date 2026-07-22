"""Local NER via spaCy (en_core_web_sm) — free, offline, the default."""

from __future__ import annotations

import asyncio
from functools import lru_cache
from typing import List

from app.core.nlp.base import NlpProvider


@lru_cache(maxsize=1)
def _get_spacy():
    import spacy

    return spacy.load("en_core_web_sm")


class LocalNlpProvider(NlpProvider):
    async def extract_entities(self, text: str) -> List[dict]:
        if not text or not text.strip():
            return []
        return await asyncio.to_thread(self._ner, text)

    @staticmethod
    def _ner(text: str) -> List[dict]:
        nlp = _get_spacy()
        doc = nlp(text[:100000])
        return [{"text": ent.text, "type": ent.label_} for ent in doc.ents]
