"""
Storage-provider factory. Select the backend via `settings.STORAGE_PROVIDER`:
  - "local"            → LocalStorageProvider (filesystem volume) — default
  - "catalyst_stratus" → StratusStorageProvider (added once Catalyst is provisioned)
  - "gcs"              → GCSStorageProvider (future, for the GCP path)

Call sites use `get_storage_provider()` and never import a concrete provider.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import settings
from app.core.storage.base import StorageProvider
from app.core.storage.local import LocalStorageProvider

__all__ = ["StorageProvider", "get_storage_provider"]


@lru_cache(maxsize=1)
def get_storage_provider() -> StorageProvider:
    provider = getattr(settings, "STORAGE_PROVIDER", "local")

    if provider == "local":
        return LocalStorageProvider(settings.UPLOAD_DIR)

    if provider == "catalyst_stratus":
        # Imported lazily so the Catalyst SDK is only required when actually selected.
        from app.core.storage.stratus import StratusStorageProvider

        return StratusStorageProvider(
            bucket=settings.STRATUS_BUCKET,
            project_id=settings.CATALYST_PROJECT_ID,
        )

    if provider == "gcs":
        # Imported lazily so google-cloud-storage is only required when actually selected.
        from app.core.storage.gcs import GCSStorageProvider

        return GCSStorageProvider(
            bucket=settings.GCS_BUCKET,
            project_id=settings.GCS_PROJECT_ID or settings.VERTEX_PROJECT_ID,
        )

    raise ValueError(f"Unknown STORAGE_PROVIDER: {provider!r}")
