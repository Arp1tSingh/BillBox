"""Household routes."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.auth import get_current_user
from app.deps import get_household_header, get_household_service
from app.domain import AuthUser
from app.schemas.households import HouseholdCreate, HouseholdJoin, HouseholdView
from app.services.households import HouseholdService

router = APIRouter(prefix="/households", tags=["households"])

UserDep = Annotated[AuthUser, Depends(get_current_user)]
ServiceDep = Annotated[HouseholdService, Depends(get_household_service)]
HouseholdHeader = Annotated[UUID | None, Depends(get_household_header)]


@router.post("", response_model=HouseholdView, status_code=status.HTTP_201_CREATED)
async def create_household(
    payload: HouseholdCreate,
    user: UserDep,
    service: ServiceDep,
) -> HouseholdView:
    return await service.create(user, payload.name)


@router.post("/join", response_model=HouseholdView)
async def join_household(
    payload: HouseholdJoin,
    user: UserDep,
    service: ServiceDep,
) -> HouseholdView:
    return await service.join(user, payload.invite_code)


@router.get("/me", response_model=HouseholdView)
async def my_household(
    user: UserDep,
    service: ServiceDep,
    household_header: HouseholdHeader,
) -> HouseholdView:
    return await service.get_for_user(user, household_header)


@router.post("/rotate-invite", response_model=HouseholdView)
async def rotate_invite(
    user: UserDep,
    service: ServiceDep,
) -> HouseholdView:
    return await service.rotate_invite(user)
