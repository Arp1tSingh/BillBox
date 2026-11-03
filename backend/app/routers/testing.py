"""Test-only helpers. Mounted only when ENVIRONMENT=test."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth import get_current_user
from app.deps import get_household_header, get_receipt_service
from app.domain import AuthUser
from app.errors import NotFoundError
from app.schemas.receipts import ReceiptDetailView
from app.services.receipts import ReceiptService

router = APIRouter(prefix="/test", tags=["testing"])

UserDep = Annotated[AuthUser, Depends(get_current_user)]
ServiceDep = Annotated[ReceiptService, Depends(get_receipt_service)]
HouseholdHeader = Annotated[UUID | None, Depends(get_household_header)]


@router.post("/receipts/{receipt_id}/fail", response_model=ReceiptDetailView)
async def force_receipt_failure(
    receipt_id: UUID,
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> ReceiptDetailView:
    """Mark a receipt failed so E2E can exercise the Retry path."""
    membership = await service.households.require_membership(user, household_header)
    receipt = await service.repo.get_receipt(receipt_id, membership.household_id)
    if receipt is None:
        raise NotFoundError("Receipt not found.", "receipt_not_found")
    await service.repo.update_receipt(
        receipt_id,
        membership.household_id,
        {
            "status": "failed",
            "failure_reason": "AI quota reached",
            "processing_started_at": None,
            "processed_at": datetime.now(UTC).isoformat(),
        },
    )
    return await service.detail(user, receipt_id, household_header=household_header)


class TestReceiptSeed(BaseModel):
    title: str | None = None
    merchant: str | None = None
    amount: Decimal | None = Field(default=None, ge=0)
    bill_date: date | None = None
    raw_text: str | None = None
    bill_type: str | None = None
    tags: list[str] = Field(default_factory=list)


@router.post("/receipts", response_model=ReceiptDetailView)
async def seed_receipt(
    payload: TestReceiptSeed,
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> ReceiptDetailView:
    """Create a ready receipt with fields and tag slugs for search E2E."""
    membership = await service.households.require_membership(user, household_header)
    receipt = await service.repo.create_receipt(
        household_id=membership.household_id,
        created_by=user.id,
        status="ready",
        processed_at=datetime.now(UTC).isoformat(),
    )
    await service.repo.update_receipt(
        receipt.id,
        membership.household_id,
        {
            "title": payload.title,
            "merchant": payload.merchant,
            "amount": str(payload.amount) if payload.amount is not None else None,
            "bill_date": payload.bill_date.isoformat() if payload.bill_date else None,
            "raw_text": payload.raw_text,
            "bill_type": payload.bill_type,
        },
    )
    tags = {tag.slug: tag for tag in await service.repo.list_tags(membership.household_id)}
    for slug in payload.tags:
        tag = tags.get(slug)
        if tag is not None:
            await service.repo.upsert_receipt_tag(
                receipt_id=receipt.id, tag_id=tag.id, source="rule", confidence=1.0
            )
    return await service.detail(user, receipt.id, household_header=household_header)
