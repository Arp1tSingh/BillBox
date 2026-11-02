"""Request and response models for the household API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

Role = Literal["owner", "member"]


class HouseholdCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)

    @field_validator("name")
    @classmethod
    def _trim(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Household name cannot be empty.")
        return value


class HouseholdJoin(BaseModel):
    invite_code: str = Field(min_length=1, max_length=32)


class MemberView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: UUID
    email: str | None = None
    role: Role
    joined_at: datetime


class HouseholdView(BaseModel):
    id: UUID
    name: str
    invite_code: str
    role: Role
    created_at: datetime
    members: list[MemberView]


class HealthView(BaseModel):
    status: str
    service: str
    environment: str
