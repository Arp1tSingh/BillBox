"""Small domain objects shared by the repository, service and API layers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

Role = Literal["owner", "member"]


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
