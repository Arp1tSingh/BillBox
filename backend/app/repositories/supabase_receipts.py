"""Supabase/PostgREST implementation of the receipts repository."""

from __future__ import annotations

import asyncio
import difflib
import logging
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from supabase import AsyncClient, create_async_client

from app.domain import Receipt, ReceiptPage, ReceiptTag, Tag
from app.repositories.base import ReceiptsRepository, RepositoryError

logger = logging.getLogger(__name__)

_RECEIPT_COLUMNS = (
    "id,household_id,created_by,title,merchant,amount,currency,bill_date,bill_type,"
    "language,status,raw_text,extracted,ai_skipped,failure_reason,"
    "processing_started_at,processed_at,created_at,updated_at"
)
_PAGE_COLUMNS = "id,receipt_id,page_no,storage_path,mime_type,size_bytes"
_TAG_COLUMNS = "id,household_id,slug,label_en,label_hi,label_mr,kind,keywords"


def _uuid(value: Any) -> UUID | None:
    return UUID(value) if value else None


def _datetime(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def _date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


def _decimal(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _receipt(row: dict[str, Any]) -> Receipt:
    return Receipt(
        id=UUID(row["id"]),
        household_id=UUID(row["household_id"]),
        created_by=_uuid(row.get("created_by")),
        title=row.get("title"),
        merchant=row.get("merchant"),
        amount=_decimal(row.get("amount")),
        currency=row.get("currency") or "INR",
        bill_date=_date(row.get("bill_date")),
        bill_type=row.get("bill_type"),
        language=row.get("language"),
        status=row["status"],
        raw_text=row.get("raw_text"),
        extracted=row.get("extracted"),
        ai_skipped=bool(row.get("ai_skipped")),
        failure_reason=row.get("failure_reason"),
        processing_started_at=_datetime(row.get("processing_started_at")),
        processed_at=_datetime(row.get("processed_at")),
        created_at=_datetime(row["created_at"]) or datetime.now(UTC),
        updated_at=_datetime(row.get("updated_at")) or datetime.now(UTC),
    )


def _page(row: dict[str, Any]) -> ReceiptPage:
    return ReceiptPage(
        id=UUID(row["id"]),
        receipt_id=UUID(row["receipt_id"]),
        page_no=int(row["page_no"]),
        storage_path=row["storage_path"],
        mime_type=row["mime_type"],
        size_bytes=int(row["size_bytes"]),
    )


def _tag(row: dict[str, Any]) -> Tag:
    return Tag(
        id=UUID(row["id"]),
        household_id=_uuid(row.get("household_id")),
        slug=row["slug"],
        label_en=row["label_en"],
        label_hi=row.get("label_hi"),
        label_mr=row.get("label_mr"),
        kind=row["kind"],
        keywords=list(row.get("keywords") or []),
    )


class SupabaseReceiptsRepository(ReceiptsRepository):
    def __init__(self, url: str, service_role_key: str) -> None:
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key
        self._client: AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _db(self) -> AsyncClient:
        if not self.service_role_key:
            raise RepositoryError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = await create_async_client(self.url, self.service_role_key)
        return self._client

    async def create_receipt(
        self,
        *,
        household_id: UUID,
        created_by: UUID,
        status: str = "processing",
        ai_skipped: bool = False,
        extracted: dict[str, object] | None = None,
        processed_at: object | None = None,
    ) -> Receipt:
        client = await self._db()
        payload: dict[str, object] = {
            "household_id": str(household_id),
            "created_by": str(created_by),
            "status": status,
            "ai_skipped": ai_skipped,
            "extracted": extracted,
        }
        if processed_at is not None:
            payload["processed_at"] = processed_at
        response = await client.table("receipts").insert(payload).execute()
        if not response.data:
            raise RepositoryError("Receipt insert returned no row.")
        return _receipt(response.data[0])

    async def add_page(
        self,
        *,
        receipt_id: UUID,
        page_no: int,
        storage_path: str,
        mime_type: str,
        size_bytes: int,
    ) -> ReceiptPage:
        client = await self._db()
        response = (
            await client.table("receipt_pages")
            .insert(
                {
                    "receipt_id": str(receipt_id),
                    "page_no": page_no,
                    "storage_path": storage_path,
                    "mime_type": mime_type,
                    "size_bytes": size_bytes,
                }
            )
            .execute()
        )
        if not response.data:
            raise RepositoryError("Receipt page insert returned no row.")
        return _page(response.data[0])

    async def list_pages(self, receipt_id: UUID) -> list[ReceiptPage]:
        client = await self._db()
        response = (
            await client.table("receipt_pages")
            .select(_PAGE_COLUMNS)
            .eq("receipt_id", str(receipt_id))
            .order("page_no")
            .execute()
        )
        return [_page(row) for row in response.data or []]

    async def get_receipt(self, receipt_id: UUID, household_id: UUID) -> Receipt | None:
        client = await self._db()
        response = (
            await client.table("receipts")
            .select(_RECEIPT_COLUMNS)
            .eq("id", str(receipt_id))
            .eq("household_id", str(household_id))
            .limit(1)
            .execute()
        )
        return _receipt(response.data[0]) if response.data else None

    async def list_receipts(self, household_id: UUID, *, limit: int = 20) -> list[Receipt]:
        client = await self._db()
        response = (
            await client.table("receipts")
            .select(_RECEIPT_COLUMNS)
            .eq("household_id", str(household_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [_receipt(row) for row in response.data or []]

    async def claim_receipt(
        self, receipt_id: UUID, household_id: UUID, *, stale_after_seconds: int
    ) -> Receipt | None:
        client = await self._db()
        now = datetime.now(UTC)
        stale_before = (now - timedelta(seconds=stale_after_seconds)).isoformat()
        response = (
            await client.table("receipts")
            .update(
                {
                    "status": "processing",
                    "processing_started_at": now.isoformat(),
                    "failure_reason": None,
                }
            )
            .eq("id", str(receipt_id))
            .eq("household_id", str(household_id))
            .in_("status", ["failed", "processing"])
            .or_(f"processing_started_at.is.null,processing_started_at.lt.{stale_before}")
            .execute()
        )
        return _receipt(response.data[0]) if response.data else None

    async def update_receipt(
        self, receipt_id: UUID, household_id: UUID, fields: dict[str, object]
    ) -> Receipt:
        client = await self._db()
        response = (
            await client.table("receipts")
            .update(fields)
            .eq("id", str(receipt_id))
            .eq("household_id", str(household_id))
            .execute()
        )
        if not response.data:
            raise RepositoryError("Receipt not found while updating.")
        return _receipt(response.data[0])

    async def delete_receipt(self, receipt_id: UUID, household_id: UUID) -> None:
        client = await self._db()
        await (
            client.table("receipts")
            .delete()
            .eq("id", str(receipt_id))
            .eq("household_id", str(household_id))
            .execute()
        )

    async def list_receipt_tags(self, receipt_id: UUID) -> list[ReceiptTag]:
        client = await self._db()
        response = (
            await client.table("receipt_tags")
            .select(f"source,confidence,removed_at,tags({_TAG_COLUMNS})")
            .eq("receipt_id", str(receipt_id))
            .execute()
        )
        result: list[ReceiptTag] = []
        for row in response.data or []:
            tag_row = row.get("tags")
            if not tag_row:
                continue
            result.append(
                ReceiptTag(
                    tag=_tag(tag_row),
                    source=row["source"],
                    confidence=(
                        float(row["confidence"])
                        if row.get("confidence") is not None
                        else None
                    ),
                    removed_at=_datetime(row.get("removed_at")),
                )
            )
        return result

    async def list_tags(self, household_id: UUID) -> list[Tag]:
        client = await self._db()
        response = (
            await client.table("tags")
            .select(_TAG_COLUMNS)
            .or_(f"household_id.is.null,household_id.eq.{household_id}")
            .order("kind")
            .order("label_en")
            .execute()
        )
        return [_tag(row) for row in response.data or []]

    async def find_tag_by_slug(self, household_id: UUID, slug: str) -> Tag | None:
        client = await self._db()
        response = (
            await client.table("tags")
            .select(_TAG_COLUMNS)
            .or_(f"household_id.is.null,household_id.eq.{household_id}")
            .eq("slug", slug)
            .limit(1)
            .execute()
        )
        return _tag(response.data[0]) if response.data else None

    async def create_tag(
        self,
        *,
        household_id: UUID,
        slug: str,
        label_en: str,
        kind: str,
        keywords: list[str] | None = None,
    ) -> Tag:
        client = await self._db()
        try:
            response = (
                await client.table("tags")
                .insert(
                    {
                        "household_id": str(household_id),
                        "slug": slug,
                        "label_en": label_en,
                        "kind": kind,
                        "keywords": keywords or [],
                    }
                )
                .execute()
            )
        except Exception as exc:
            existing = await self.find_tag_by_slug(household_id, slug)
            if existing is not None:
                return existing
            raise RepositoryError("Could not create tag.") from exc
        if not response.data:
            raise RepositoryError("Tag insert returned no row.")
        return _tag(response.data[0])

    async def upsert_receipt_tag(
        self,
        *,
        receipt_id: UUID,
        tag_id: UUID,
        source: str,
        confidence: float | None = None,
        user_id: UUID | None = None,
    ) -> None:
        client = await self._db()
        await (
            client.table("receipt_tags")
            .upsert(
                {
                    "receipt_id": str(receipt_id),
                    "tag_id": str(tag_id),
                    "source": source,
                    "confidence": confidence,
                    "removed_at": None,
                    "removed_by": str(user_id) if user_id else None,
                },
                on_conflict="receipt_id,tag_id",
            )
            .execute()
        )

    async def remove_receipt_tag(
        self, *, receipt_id: UUID, tag_id: UUID, user_id: UUID | None = None
    ) -> None:
        client = await self._db()
        await (
            client.table("receipt_tags")
            .update(
                {
                    "removed_at": datetime.now(UTC).isoformat(),
                    "removed_by": str(user_id) if user_id else None,
                }
            )
            .eq("receipt_id", str(receipt_id))
            .eq("tag_id", str(tag_id))
            .execute()
        )

    async def find_similar_merchant_tag(
        self, household_id: UUID, merchant: str, *, threshold: float = 0.6
    ) -> Tag | None:
        client = await self._db()
        response = (
            await client.table("tags")
            .select(_TAG_COLUMNS)
            .eq("household_id", str(household_id))
            .eq("kind", "merchant")
            .execute()
        )
        target = merchant.casefold()
        best: tuple[float, Tag] | None = None
        for row in response.data or []:
            tag = _tag(row)
            ratio = difflib.SequenceMatcher(None, target, tag.label_en.casefold()).ratio()
            if ratio > threshold and (best is None or ratio > best[0]):
                best = (ratio, tag)
        return best[1] if best else None
