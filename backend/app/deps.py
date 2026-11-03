"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Header, Request

from app.errors import ConfigError
from app.services.households import HouseholdService
from app.services.receipts import ReceiptService
from app.services.search import SearchService
from app.services.tags import TagService


def get_household_service(request: Request) -> HouseholdService:
    service = getattr(request.app.state, "household_service", None)
    if service is None:
        raise ConfigError("The household service is not configured.")
    return service


async def get_household_header(
    x_household_id: Annotated[UUID | None, Header(alias="X-Household-Id")] = None,
) -> UUID | None:
    return x_household_id


def get_receipt_service(request: Request) -> ReceiptService:
    service = getattr(request.app.state, "receipt_service", None)
    if service is None:
        raise ConfigError("The receipt service is not configured.")
    return service


def get_tag_service(request: Request) -> TagService:
    service = getattr(request.app.state, "tag_service", None)
    if service is None:
        raise ConfigError("The tag service is not configured.")
    return service


def get_search_service(request: Request) -> SearchService:
    service = getattr(request.app.state, "search_service", None)
    if service is None:
        raise ConfigError("The search service is not configured.")
    return service
