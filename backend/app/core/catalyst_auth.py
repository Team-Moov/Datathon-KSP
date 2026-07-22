"""
Shared Catalyst OAuth admin-token manager.

REST-based Catalyst service adapters (Stratus, Cache, ...) all authenticate the
same way: a Zoho self-client refresh token exchanged for a short-lived access
token, sent as `Authorization: Zoho-oauthtoken <token>`. This centralises that so
each adapter doesn't re-implement (and re-refresh) it.

Credentials come from settings (see config.py): CATALYST_DC, CATALYST_CLIENT_ID,
CATALYST_CLIENT_SECRET, CATALYST_REFRESH_TOKEN. Data center is "in" for this account.
"""

from __future__ import annotations

import time
from typing import Optional

import httpx

from app.core.config import settings


class CatalystTokenManager:
    """Mints and caches a Zoho OAuth access token from the refresh token."""

    def __init__(self) -> None:
        dc = getattr(settings, "CATALYST_DC", "in")
        self._accounts_url = f"https://accounts.zoho.{dc}/oauth/v2/token"
        self._client_id = settings.CATALYST_CLIENT_ID
        self._client_secret = settings.CATALYST_CLIENT_SECRET
        self._refresh_token = settings.CATALYST_REFRESH_TOKEN
        self._token: Optional[str] = None
        self._expires_at: float = 0.0

    async def token(self) -> str:
        if self._token and time.time() < self._expires_at - 60:
            return self._token
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                self._accounts_url,
                params={
                    "refresh_token": self._refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "grant_type": "refresh_token",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        if "access_token" not in data:
            raise RuntimeError(f"Zoho token refresh failed: {data}")
        self._token = data["access_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 3600))
        return self._token


_manager: Optional[CatalystTokenManager] = None


def get_catalyst_token_manager() -> CatalystTokenManager:
    global _manager
    if _manager is None:
        _manager = CatalystTokenManager()
    return _manager


async def catalyst_auth_header() -> dict:
    return {"Authorization": f"Zoho-oauthtoken {await get_catalyst_token_manager().token()}"}
