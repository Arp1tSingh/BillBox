"""Test-only helpers. Mounted only when ENVIRONMENT=test."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

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
