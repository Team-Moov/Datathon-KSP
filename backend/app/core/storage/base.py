"""
Provider-agnostic object storage interface.

The app stores uploaded documents, generated report PDFs, and (later) audio blobs.
Today that lives on a local filesystem volume; the deployment target may move it to
Catalyst Stratus or GCS. Everything goes through this interface so the backend
(swap `STORAGE_PROVIDER`) rather than editing call sites.

A `ref` is an opaque string persisted on the record (e.g. `Document.raw_file_ref`).
Only the provider that issued a ref knows how to resolve it — call sites never parse it.
"""

from __future__ import annotations

import os
import tempfile
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional


class StorageProvider(ABC):
    """Store/retrieve opaque blobs by key. Local now; Stratus/GCS later."""

    @abstractmethod
    async def put(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        """Store `content` under `key`; return an opaque ref string to persist."""

    @abstractmethod
    async def get(self, ref: str) -> bytes:
        """Return the bytes for a ref previously returned by `put`."""

    @abstractmethod
    async def delete(self, ref: str) -> None:
        """Delete the object; no error if it is already gone."""

    @asynccontextmanager
    async def local_path(self, ref: str, suffix: str = "") -> AsyncIterator[Path]:
        """
        Yield a real on-disk path for a ref, so code that needs a filesystem path
        (extractors, pdf tooling) works regardless of backend.

        Default implementation downloads the object to a temp file and cleans it up —
        correct for any remote backend. `LocalStorageProvider` overrides this to
        hand back the real path with no copy.
        """
        data = await self.get(ref)
        fd, tmp = tempfile.mkstemp(suffix=suffix)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
            yield Path(tmp)
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass
