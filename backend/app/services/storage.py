"""Private receipt storage (Supabase Storage or an in-memory test double)."""

from __future__ import annotations

import logging
from typing import Protocol
from uuid import uuid4

from supabase import AsyncClient, create_async_client

from app.repositories.base import RepositoryError

logger = logging.getLogger(__name__)

BUCKET = "receipts"


class StorageService(Protocol):
    async def upload(self, path: str, data: bytes, content_type: str) -> None: ...

    async def download(self, path: str) -> bytes: ...

    async def signed_url(self, path: str, *, expires_in: int = 3600) -> str: ...

    async def delete(self, paths: list[str]) -> None: ...


def build_storage_path(household_id: object, receipt_id: object, page_no: int, ext: str) -> str:
    return f"{household_id}/{receipt_id}/{page_no}-{uuid4().hex}.{ext}"


class SupabaseStorageService(StorageService):
    def __init__(self, url: str, service_role_key: str, *, bucket: str = BUCKET) -> None:
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key
        self.bucket = bucket
        self._client: AsyncClient | None = None

    async def _storage(self):
        if not self.service_role_key:
            raise RepositoryError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
        if self._client is None:
            self._client = await create_async_client(self.url, self.service_role_key)
        return self._client.storage.from_(self.bucket)

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        storage = await self._storage()
        await storage.upload(path, data, {"content-type": content_type, "upsert": "false"})

    async def download(self, path: str) -> bytes:
        storage = await self._storage()
        return await storage.download(path)

    async def signed_url(self, path: str, *, expires_in: int = 3600) -> str:
        storage = await self._storage()
        response = await storage.create_signed_url(path, expires_in)
        if isinstance(response, dict):
            return str(
                response.get("signedURL")
                or response.get("signedUrl")
                or response.get("signed_url")
                or ""
            )
        return str(getattr(response, "signed_url", "") or getattr(response, "signedURL", ""))

    async def delete(self, paths: list[str]) -> None:
        if not paths:
            return
        storage = await self._storage()
        await storage.remove(paths)
