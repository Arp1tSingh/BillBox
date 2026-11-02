"""In-memory household repository for fast API tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.domain import Household, MemberRecord, Membership
from app.repositories.base import (
    AlreadyMemberError,
    HouseholdFullError,
    InviteCodeTakenError,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


class FakeHouseholdsRepository:
    def __init__(self, *, max_members: int = 8) -> None:
        self.max_members = max_members
        self.households: dict[UUID, Household] = {}
        self.memberships: dict[UUID, Membership] = {}
        self.members: dict[UUID, list[MemberRecord]] = {}
        self.emails: dict[UUID, str] = {}

    def set_email(self, user_id: UUID, email: str) -> None:
        self.emails[user_id] = email

    async def get_membership(self, user_id: UUID) -> Membership | None:
        return self.memberships.get(user_id)

    async def get_household(self, household_id: UUID) -> Household | None:
        return self.households.get(household_id)

    async def list_members(self, household_id: UUID) -> list[MemberRecord]:
        return list(self.members.get(household_id, []))

    async def create_household(
        self, *, name: str, invite_code: str, created_by: UUID
    ) -> Household:
        if any(h.invite_code == invite_code for h in self.households.values()):
            raise InviteCodeTakenError()
        if created_by in self.memberships:
            raise AlreadyMemberError()
        household = Household(
            id=uuid4(),
            name=name,
            invite_code=invite_code,
            created_by=created_by,
            created_at=_now(),
        )
        self.households[household.id] = household
        try:
            await self.add_member(
                household_id=household.id, user_id=created_by, role="owner"
            )
        except Exception:
            self.households.pop(household.id, None)
            raise
        return household

    async def add_member(
        self, *, household_id: UUID, user_id: UUID, role: str = "member"
    ) -> Membership:
        if user_id in self.memberships:
            raise AlreadyMemberError()
        if household_id not in self.households:
            raise KeyError("Household not found")
        if len(self.members.get(household_id, [])) >= self.max_members:
            raise HouseholdFullError()
        membership = Membership(
            household_id=household_id,
            user_id=user_id,
            role=role,  # type: ignore[arg-type]
            created_at=_now(),
        )
        self.memberships[user_id] = membership
        self.members.setdefault(household_id, []).append(
            MemberRecord(
                user_id=user_id,
                role=role,  # type: ignore[arg-type]
                created_at=membership.created_at,
                email=self.emails.get(user_id),
            )
        )
        return membership

    async def count_members(self, household_id: UUID) -> int:
        return len(self.members.get(household_id, []))

    async def find_by_invite_code(self, invite_code: str) -> Household | None:
        return next(
            (h for h in self.households.values() if h.invite_code == invite_code),
            None,
        )

    async def update_invite_code(self, *, household_id: UUID, invite_code: str) -> Household:
        if any(
            h.id != household_id and h.invite_code == invite_code
            for h in self.households.values()
        ):
            raise InviteCodeTakenError()
        household = self.households[household_id]
        updated = replace(household, invite_code=invite_code)
        self.households[household_id] = updated
        return updated

    async def delete_household(self, household_id: UUID) -> None:
        self.households.pop(household_id, None)
        self.members.pop(household_id, None)
        for user_id, membership in list(self.memberships.items()):
            if membership.household_id == household_id:
                del self.memberships[user_id]
