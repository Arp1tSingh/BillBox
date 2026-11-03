"""Small domain objects shared by the repository, service and API layers."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

Role = Literal["owner", "member"]
ReceiptStatus = Literal["processing", "ready", "failed"]
TagKind = Literal["bill_type", "merchant", "custom"]
TagSource = Literal["rule", "ai", "user"]
Language = Literal["en", "hi", "mr", "mixed", "other"]


@dataclass(frozen=True, slots=True)
class AuthUser:
    id: UUID
    email: str | None = None
    role: str | None = None


@dataclass(frozen=True, slots=True)
class Household:
    id: UUID
    name: str
    invite_code: str
    created_by: UUID | None
    created_at: str


@dataclass(frozen=True, slots=True)
class Membership:
    household_id: UUID
    user_id: UUID
    role: Role
    created_at: str


@dataclass(frozen=True, slots=True)
class MemberRecord:
    user_id: UUID
    role: Role
    created_at: str
    email: str | None = None


@dataclass(frozen=True, slots=True)
class Receipt:
    id: UUID
    household_id: UUID
    created_by: UUID | None
    title: str | None
    merchant: str | None
    amount: Decimal | None
    currency: str
    bill_date: date | None
    bill_type: str | None
    language: str | None
    status: ReceiptStatus
    raw_text: str | None
    extracted: dict[str, Any] | None
    ai_skipped: bool
    failure_reason: str | None
    processing_started_at: datetime | None
    processed_at: datetime | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class ReceiptPage:
    id: UUID
    receipt_id: UUID
    page_no: int
    storage_path: str
    mime_type: str
    size_bytes: int


@dataclass(frozen=True, slots=True)
class Tag:
    id: UUID
    household_id: UUID | None
    slug: str
    label_en: str
    label_hi: str | None
    label_mr: str | None
    kind: TagKind
    keywords: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ReceiptTag:
    tag: Tag
    source: TagSource
    confidence: float | None = None
    removed_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class ExtractionResult:
    bill_type: str | None
    merchant: str | None
    amount: Decimal | None
    currency: str | None
    bill_date: date | None
    language: str | None
    raw_text: str | None
    tags: list[str] = field(default_factory=list)
