"""Household persistence contract.

The Supabase implementation is the production adapter; tests use an in-memory
fake. Keeping this interface small makes the business rules testable without a
database.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain import Household, MemberRecord, Membership


class RepositoryError(Exception):
    """Unexpected persistence failure."""


class AlreadyMemberError(RepositoryError):
    """The user already belongs to a household."""


class HouseholdFullError(RepositoryError):
    """The household has reached its member cap."""


class InviteCodeTakenError(RepositoryError):
    """The generated invite code collided with an existing household."""


class HouseholdsRepository(Protocol):
    async def get_membership(self, user_id: UUID) -> Membership | None: ...

    async def get_household(self, household_id: UUID) -> Household | None: ...

    async def list_members(self, household_id: UUID) -> list[MemberRecord]: ...

    async def create_household(
        self, *, name: str, invite_code: str, created_by: UUID
    ) -> Household:
        """Create the household and its owner membership atomically."""
        ...

    async def add_member(
        self, *, household_id: UUID, user_id: UUID, role: str = "member"
    ) -> Membership: ...

    async def count_members(self, household_id: UUID) -> int: ...

    async def find_by_invite_code(self, invite_code: str) -> Household | None: ...

    async def update_invite_code(self, *, household_id: UUID, invite_code: str) -> Household: ...

    async def delete_household(self, household_id: UUID) -> None: ...
