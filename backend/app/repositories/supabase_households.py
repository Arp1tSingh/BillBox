"""Supabase/PostgREST implementation of the household repository."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

import httpx
from supabase import AsyncClient, create_async_client

from app.domain import Household, MemberRecord, Membership
from app.repositories.base import (
    AlreadyMemberError,
    HouseholdFullError,
    HouseholdsRepository,
    InviteCodeTakenError,
    RepositoryError,
)

logger = logging.getLogger(__name__)


def _error_code(exc: Exception) -> str | None:
    return getattr(exc, "code", None)


def _error_text(exc: Exception) -> str:
    parts = [
        str(getattr(exc, "message", "") or ""),
        str(getattr(exc, "details", "") or ""),
        str(getattr(exc, "hint", "") or ""),
        str(exc),
    ]
    return " ".join(parts).lower()


def _household(row: dict[str, Any]) -> Household:
    return Household(
        id=UUID(row["id"]),
        name=row["name"],
        invite_code=row["invite_code"],
        created_by=UUID(row["created_by"]) if row.get("created_by") else None,
        created_at=row["created_at"],
    )


def _membership(row: dict[str, Any]) -> Membership:
    return Membership(
        household_id=UUID(row["household_id"]),
        user_id=UUID(row["user_id"]),
        role=row["role"],
        created_at=row["created_at"],
    )


class SupabaseHouseholdsRepository(HouseholdsRepository):
    def __init__(self, url: str, service_role_key: str) -> None:
        self.url = url.rstrip("/")
        self.service_role_key = service_role_key
        self._client: AsyncClient | None = None
        self._client_lock = asyncio.Lock()

    async def _db(self) -> AsyncClient:
        if not self.service_role_key:
            raise RepositoryError("SUPABASE_SERVICE_ROLE_KEY is not configured.")
        if self._client is None:
            async with self._client_lock:
                if self._client is None:
                    self._client = await create_async_client(self.url, self.service_role_key)
        return self._client

    async def get_membership(self, user_id: UUID) -> Membership | None:
        client = await self._db()
        response = (
            await client.table("household_members")
            .select("household_id,user_id,role,created_at")
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
        return _membership(response.data[0]) if response.data else None

    async def get_household(self, household_id: UUID) -> Household | None:
        client = await self._db()
        response = (
            await client.table("households")
            .select("id,name,invite_code,created_by,created_at")
            .eq("id", str(household_id))
            .limit(1)
            .execute()
        )
        return _household(response.data[0]) if response.data else None

    async def list_members(self, household_id: UUID) -> list[MemberRecord]:
        client = await self._db()
        response = (
            await client.table("household_members")
            .select("user_id,role,created_at")
            .eq("household_id", str(household_id))
            .order("created_at")
            .execute()
        )
        rows = response.data or []
        emails = await asyncio.gather(*(self._fetch_email(UUID(row["user_id"])) for row in rows))
        return [
            MemberRecord(
                user_id=UUID(row["user_id"]),
                role=row["role"],
                created_at=row["created_at"],
                email=email,
            )
            for row, email in zip(rows, emails, strict=True)
        ]

    async def create_household(
        self, *, name: str, invite_code: str, created_by: UUID
    ) -> Household:
        client = await self._db()
        try:
            response = (
                await client.table("households")
                .insert(
                    {
                        "name": name,
                        "invite_code": invite_code,
                        "created_by": str(created_by),
                    }
                )
                .execute()
            )
        except Exception as exc:
            if _error_code(exc) == "23505" and "invite_code" in _error_text(exc):
                raise InviteCodeTakenError() from exc
            raise RepositoryError("Could not create household.") from exc

        if not response.data:
            raise RepositoryError("Household insert returned no row.")
        household = _household(response.data[0])

        try:
            await self.add_member(
                household_id=household.id,
                user_id=created_by,
                role="owner",
            )
        except Exception:
            # Do not leave a household with no owner behind.
            await client.table("households").delete().eq("id", str(household.id)).execute()
            raise
        return household

    async def add_member(
        self, *, household_id: UUID, user_id: UUID, role: str = "member"
    ) -> Membership:
        client = await self._db()
        try:
            response = (
                await client.table("household_members")
                .insert(
                    {
                        "household_id": str(household_id),
                        "user_id": str(user_id),
                        "role": role,
                    }
                )
                .execute()
            )
        except Exception as exc:
            text = _error_text(exc)
            if "household_full" in text:
                raise HouseholdFullError() from exc
            if _error_code(exc) == "23505":
                raise AlreadyMemberError() from exc
            raise RepositoryError("Could not add household member.") from exc

        if not response.data:
            raise RepositoryError("Membership insert returned no row.")
        return _membership(response.data[0])

    async def count_members(self, household_id: UUID) -> int:
        client = await self._db()
        response = (
            await client.table("household_members")
            .select("user_id", count="exact")
            .eq("household_id", str(household_id))
            .execute()
        )
        return int(response.count if response.count is not None else len(response.data or []))

    async def find_by_invite_code(self, invite_code: str) -> Household | None:
        client = await self._db()
        response = (
            await client.table("households")
            .select("id,name,invite_code,created_by,created_at")
            .eq("invite_code", invite_code)
            .limit(1)
            .execute()
        )
        return _household(response.data[0]) if response.data else None

    async def update_invite_code(self, *, household_id: UUID, invite_code: str) -> Household:
        client = await self._db()
        try:
            response = (
                await client.table("households")
                .update({"invite_code": invite_code})
                .eq("id", str(household_id))
                .execute()
            )
        except Exception as exc:
            if _error_code(exc) == "23505" and "invite_code" in _error_text(exc):
                raise InviteCodeTakenError() from exc
            raise RepositoryError("Could not rotate invite code.") from exc

        if not response.data:
            raise RepositoryError("Household not found while rotating invite code.")
        return _household(response.data[0])

    async def delete_household(self, household_id: UUID) -> None:
        client = await self._db()
        await client.table("households").delete().eq("id", str(household_id)).execute()

    async def _fetch_email(self, user_id: UUID) -> str | None:
        if not self.service_role_key:
            return None
        headers = {
            "apikey": self.service_role_key,
            "Authorization": f"Bearer {self.service_role_key}",
        }
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.get(
                    f"{self.url}/auth/v1/admin/users/{user_id}",
                    headers=headers,
                )
            if response.status_code == 200:
                return response.json().get("email")
        except httpx.HTTPError:
            logger.info("member_email_lookup_failed", extra={"user_id": str(user_id)})
        return None
