"""
Catalyst Zia OCR provider (REST-based, shared Catalyst OAuth).

Endpoint (from the zcatalyst-sdk source): POST {api_base}/baas/v1/project/{id}/ml/ocr
with a multipart `image` field and optional language/modelType. Returns
{confidence, text}. Scope: ZohoCatalyst.mlkit.READ. Supports 10 Indian languages
and .jpg/.png/.tiff/.bmp/.pdf up to 20 MB; Catalyst does not store the upload.
"""

from __future__ import annotations

from typing import Optional

import httpx
import structlog

from app.core.catalyst_auth import catalyst_auth_header
from app.core.config import settings
from app.core.ocr.base import OcrProvider

log = structlog.get_logger(__name__)


class ZiaOcrProvider(OcrProvider):
    def __init__(self, project_id: str) -> None:
        if not project_id:
            raise RuntimeError("CATALYST_PROJECT_ID is required for Zia OCR")
        dc = getattr(settings, "CATALYST_DC", "in")
        api_base = getattr(settings, "CATALYST_API_BASE", "") or f"https://api.catalyst.zoho.{dc}"
        self.endpoint = f"{api_base}/baas/v1/project/{project_id}/ml/ocr"

    async def extract_text(
        self, content: bytes, filename: str, language: Optional[str] = None
    ) -> dict:
        data = {"modelType": "OCR"}
        if language:
            data["language"] = language
        files = {"image": (filename, content)}
        async with httpx.AsyncClient(timeout=90) as client:
            resp = await client.post(
                self.endpoint, headers=await catalyst_auth_header(), files=files, data=data
            )
            resp.raise_for_status()
            body = resp.json().get("data", {}) or {}
        log.info("Zia OCR extracted", chars=len(body.get("text", "")), confidence=body.get("confidence"))
        return {
            "text": body.get("text", ""),
            "confidence": body.get("confidence"),
            "provider": "zia",
        }
