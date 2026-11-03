"""Tag routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.auth import get_current_user
from app.deps import get_household_header, get_tag_service
from app.domain import AuthUser
from app.schemas.tags import TagView
from app.services.tags import TagService

router = APIRouter(prefix="/tags", tags=["tags"])

UserDep = Annotated[AuthUser, Depends(get_current_user)]
ServiceDep = Annotated[TagService, Depends(get_tag_service)]
HouseholdHeader = Annotated[UUID | None, Depends(get_household_header)]


@router.get("", response_model=list[TagView])
async def list_tags(
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> list[TagView]:
    return await service.list_for_user(user, household_header)
