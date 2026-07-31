"""Local-filesystem storage provider — the default, and the current behaviour."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

from app.core.storage.base import StorageProvider


class LocalStorageProvider(StorageProvider):
    """
    Stores blobs under a base directory (the `/uploads` Docker volume by default).
    Refs are `local://<key>` so they are self-describing and distinguishable from
    the `seed://` and (future) `stratus://` schemes.
    """

    SCHEME = "local://"

    def __init__(self, base_dir: str) -> None:
        self.base = Path(base_dir)
        self.base.mkdir(parents=True, exist_ok=True)

    def _key(self, ref: str) -> str:
        return ref[len(self.SCHEME):] if ref.startswith(self.SCHEME) else ref

    def _resolve(self, ref: str) -> Path:
        return self.base / self._key(ref)

    async def put(self, key: str, content: bytes, content_type: Optional[str] = None) -> str:
        dest = self.base / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        # Offload the blocking write so the event loop isn't stalled on large files.
        await asyncio.to_thread(dest.write_bytes, content)
        return f"{self.SCHEME}{key}"

    async def get(self, ref: str) -> bytes:
        return await asyncio.to_thread(self._resolve(ref).read_bytes)

    async def delete(self, ref: str) -> None:
        path = self._resolve(ref)
        if path.exists():
            await asyncio.to_thread(path.unlink)

    @asynccontextmanager
    async def local_path(self, ref: str, suffix: str = "") -> AsyncIterator[Path]:
        # Already on disk — hand back the real path, no temp copy.
        yield self._resolve(ref)
