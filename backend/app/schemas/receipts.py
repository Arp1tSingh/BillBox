"""Request and response models for the receipts API."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

ReceiptStatus = Literal["processing", "ready", "failed"]


class ReceiptPageView(BaseModel):
    page_no: int
    mime_type: str
    size_bytes: int
    url: str | None = None


class ReceiptTagView(BaseModel):
    tag_id: UUID
    slug: str
    label_en: str
    label_hi: str | None = None
    label_mr: str | None = None
    kind: str
    source: str
    confidence: float | None = None


class ReceiptSummaryView(BaseModel):
    id: UUID
    title: str | None
    merchant: str | None
    amount: Decimal | None
    currency: str
    bill_date: date | None
    bill_type: str | None
    status: ReceiptStatus
    ai_skipped: bool
    failure_reason: str | None
    created_at: datetime
    thumbnail_url: str | None = None


class ReceiptDetailView(ReceiptSummaryView):
    language: str | None = None
    raw_text: str | None = None
    extracted: dict[str, Any] | None = None
    pages: list[ReceiptPageView] = Field(default_factory=list)
    tags: list[ReceiptTagView] = Field(default_factory=list)
    processed_at: datetime | None = None


class ReceiptUploadView(BaseModel):
    id: UUID
    status: ReceiptStatus


class ReceiptUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    merchant: str | None = Field(default=None, max_length=200)
    amount: Decimal | None = Field(default=None, ge=0, le=Decimal("9999999999.99"))
    bill_date: date | None = None


class ReceiptListQuery(BaseModel):
    limit: int = Field(default=20, ge=1, le=50)


class ReceiptTagCreate(BaseModel):
    tag_id: UUID | None = None
    label: str | None = Field(default=None, max_length=80)
