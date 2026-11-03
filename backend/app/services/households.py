"""Household business rules: one household per account, invite codes, cap 8."""

from __future__ import annotations

from uuid import UUID

from app.domain import AuthUser, Household, Membership, Role
from app.errors import AppError, ConflictError, ForbiddenError, NotFoundError
from app.repositories.base import (
    AlreadyMemberError,
    HouseholdFullError,
    HouseholdsRepository,
    InviteCodeTakenError,
)
from app.schemas.households import HouseholdView, MemberView
from app.services.invites import generate_invite_code, is_valid_invite_code, normalize_invite_code


class HouseholdService:
    def __init__(
        self,
        repo: HouseholdsRepository,
        *,
        max_members: int = 8,
        invite_length: int = 8,
    ) -> None:
        self.repo = repo
        self.max_members = max_members
        self.invite_length = invite_length

    async def create(self, user: AuthUser, name: str) -> HouseholdView:
        if await self.repo.get_membership(user.id) is not None:
            raise ConflictError("You are already in a household.", "already_in_household")

        clean_name = name.strip()
        if not clean_name or len(clean_name) > 80:
            raise AppError(
                422,
                "invalid_household_name",
                "Household name must be between 1 and 80 characters.",
            )

        # Invite-code collisions are vanishingly rare; retry a few times rather
        # than surfacing a confusing 409 to the user.
        for _ in range(5):
            code = generate_invite_code(self.invite_length)
            try:
                household = await self.repo.create_household(
                    name=clean_name,
                    invite_code=code,
                    created_by=user.id,
                )
            except InviteCodeTakenError:
                continue
            except AlreadyMemberError as exc:
                raise ConflictError(
                    "You are already in a household.", "already_in_household"
                ) from exc
            return await self._view(household, "owner")

        raise AppError(
            500,
            "could_not_create_household",
            "Could not create the household. Try again.",
        )

    async def join(self, user: AuthUser, raw_code: str) -> HouseholdView:
        if await self.repo.get_membership(user.id) is not None:
            raise ConflictError("You are already in a household.", "already_in_household")

        code = normalize_invite_code(raw_code)
        if not is_valid_invite_code(code, self.invite_length):
            raise NotFoundError("That invite code is not valid.", "invalid_invite_code")

        household = await self.repo.find_by_invite_code(code)
        if household is None:
            raise NotFoundError("That invite code is not valid.", "invalid_invite_code")

        if await self.repo.count_members(household.id) >= self.max_members:
            raise self._full_error()

        try:
            await self.repo.add_member(household_id=household.id, user_id=user.id)
        except HouseholdFullError as exc:
            raise self._full_error() from exc
        except AlreadyMemberError as exc:
            raise ConflictError(
                "You are already in a household.", "already_in_household"
            ) from exc

        return await self._view(household, "member")

    async def require_membership(
        self, user: AuthUser, household_header: UUID | None = None
    ) -> Membership:
        membership = await self.repo.get_membership(user.id)
        if membership is None:
            if household_header is not None:
                raise ForbiddenError("You are not a member of that household.", "not_a_member")
            raise NotFoundError("You are not in a household yet.", "no_household")
        if household_header is not None and household_header != membership.household_id:
            raise ForbiddenError("You are not a member of that household.", "not_a_member")
        return membership

    async def get_for_user(
        self, user: AuthUser, household_header: UUID | None = None
    ) -> HouseholdView:
        membership = await self.require_membership(user, household_header)

        household = await self.repo.get_household(membership.household_id)
        if household is None:
            raise NotFoundError("Your household no longer exists.", "no_household")
        return await self._view(household, membership.role)

    async def rotate_invite(self, user: AuthUser) -> HouseholdView:
        membership = await self._membership(user)
        if membership.role != "owner":
            raise ForbiddenError(
                "Only the household owner can rotate the invite code.",
                "owner_only",
            )

        for _ in range(5):
            code = generate_invite_code(self.invite_length)
            try:
                household = await self.repo.update_invite_code(
                    household_id=membership.household_id,
                    invite_code=code,
                )
            except InviteCodeTakenError:
                continue
            return await self._view(household, "owner")

        raise AppError(
            500,
            "could_not_rotate_invite",
            "Could not rotate the invite code. Try again.",
        )

    async def _membership(self, user: AuthUser) -> Membership:
        membership = await self.repo.get_membership(user.id)
        if membership is None:
            raise NotFoundError("You are not in a household yet.", "no_household")
        return membership

    async def _view(self, household: Household, role: Role) -> HouseholdView:
        members = await self.repo.list_members(household.id)
        members.sort(key=lambda member: (member.role != "owner", member.created_at))
        return HouseholdView(
            id=household.id,
            name=household.name,
            invite_code=household.invite_code,
            role=role,
            created_at=household.created_at,
            members=[
                MemberView(
                    user_id=member.user_id,
                    email=member.email,
                    role=member.role,
                    joined_at=member.created_at,
                )
                for member in members
            ],
        )

    def _full_error(self) -> ConflictError:
        return ConflictError(
            f"This household is full ({self.max_members} members max).",
            "household_full",
        )
