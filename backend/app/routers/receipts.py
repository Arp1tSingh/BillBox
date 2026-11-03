"""Receipt routes."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status

from app.auth import get_current_user
from app.deps import get_household_header, get_receipt_service, get_search_service
from app.domain import AuthUser
from app.schemas.receipts import (
    ReceiptDetailView,
    ReceiptSearchResponse,
    ReceiptTagCreate,
    ReceiptUpdate,
    ReceiptUploadView,
)
from app.services.receipts import ReceiptService
from app.services.search import SearchService

router = APIRouter(prefix="/receipts", tags=["receipts"])

UserDep = Annotated[AuthUser, Depends(get_current_user)]
ServiceDep = Annotated[ReceiptService, Depends(get_receipt_service)]
SearchDep = Annotated[SearchService, Depends(get_search_service)]
HouseholdHeader = Annotated[UUID | None, Depends(get_household_header)]


@router.post("", response_model=ReceiptUploadView, status_code=status.HTTP_202_ACCEPTED)
async def upload_receipt(
    files: Annotated[list[UploadFile], File(alias="files[]")],
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
    skip_ai: Annotated[bool, Form()] = False,
) -> ReceiptUploadView:
    return await service.upload(
        user, files, skip_ai=skip_ai, household_header=household_header
    )


@router.post("/{receipt_id}/process", response_model=ReceiptDetailView)
async def process_receipt(
    receipt_id: UUID,
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> ReceiptDetailView:
    return await service.process(user, receipt_id, household_header=household_header)


@router.get("", response_model=ReceiptSearchResponse)
async def list_receipts(
    user: UserDep,
    service: SearchDep,
    household_header: HouseholdHeader,
    q: Annotated[str | None, Query(max_length=200)] = None,
    tag: Annotated[list[str] | None, Query()] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    min_amount: Annotated[Decimal | None, Query(alias="min", ge=0)] = None,
    max_amount: Annotated[Decimal | None, Query(alias="max", ge=0)] = None,
    sort: Annotated[str, Query()] = "date",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=50)] = 20,
    limit: Annotated[int | None, Query(ge=1, le=50)] = None,
) -> ReceiptSearchResponse:
    return await service.search(
        user,
        q=q,
        tag=tag or [],
        date_from=date_from,
        date_to=date_to,
        min_amount=min_amount,
        max_amount=max_amount,
        sort=sort,
        page=page,
        page_size=limit or page_size,
        household_header=household_header,
    )


@router.get("/{receipt_id}", response_model=ReceiptDetailView)
async def get_receipt(
    receipt_id: UUID,
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> ReceiptDetailView:
    return await service.detail(user, receipt_id, household_header=household_header)


@router.patch("/{receipt_id}", response_model=ReceiptDetailView)
async def update_receipt(
    receipt_id: UUID,
    payload: ReceiptUpdate,
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> ReceiptDetailView:
    fields = payload.model_dump(exclude_unset=True)
    return await service.update(
        user, receipt_id, fields, household_header=household_header
    )


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_receipt(
    receipt_id: UUID,
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> None:
    await service.delete(user, receipt_id, household_header=household_header)


@router.post("/{receipt_id}/tags", response_model=ReceiptDetailView)
async def add_receipt_tag(
    receipt_id: UUID,
    payload: ReceiptTagCreate,
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> ReceiptDetailView:
    return await service.add_tag(
        user,
        receipt_id,
        tag_id=payload.tag_id,
        label=payload.label,
        household_header=household_header,
    )


@router.delete("/{receipt_id}/tags/{tag_id}", response_model=ReceiptDetailView)
async def remove_receipt_tag(
    receipt_id: UUID,
    tag_id: UUID,
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> ReceiptDetailView:
    return await service.remove_tag(
        user, receipt_id, tag_id, household_header=household_header
    )
