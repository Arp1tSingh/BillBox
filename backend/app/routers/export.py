"""Household data export."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.auth import get_current_user
from app.deps import get_export_service, get_household_header
from app.domain import AuthUser
from app.services.export import ExportService

router = APIRouter(tags=["export"])

UserDep = Annotated[AuthUser, Depends(get_current_user)]
ExportDep = Annotated[ExportService, Depends(get_export_service)]
HouseholdHeader = Annotated[UUID | None, Depends(get_household_header)]


@router.get("/households/export")
async def export_household(
    user: UserDep,
    service: ExportDep,
    household_header: HouseholdHeader,
) -> StreamingResponse:
    chunks, filename = await service.export(user, household_header=household_header)
    return StreamingResponse(
        chunks,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
