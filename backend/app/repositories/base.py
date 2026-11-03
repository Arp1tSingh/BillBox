"""Household persistence contract.

The Supabase implementation is the production adapter; tests use an in-memory
fake. Keeping this interface small makes the business rules testable without a
database.
"""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain import Household, MemberRecord, Membership, Receipt, ReceiptPage, ReceiptTag, Tag


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


class ReceiptsRepository(Protocol):
    async def create_receipt(
        self,
        *,
        household_id: UUID,
        created_by: UUID,
        status: str = "processing",
        ai_skipped: bool = False,
        extracted: dict[str, object] | None = None,
        processed_at: object | None = None,
    ) -> Receipt: ...

    async def add_page(
        self,
        *,
        receipt_id: UUID,
        page_no: int,
        storage_path: str,
        mime_type: str,
        size_bytes: int,
    ) -> ReceiptPage: ...

    async def list_pages(self, receipt_id: UUID) -> list[ReceiptPage]: ...

    async def get_receipt(self, receipt_id: UUID, household_id: UUID) -> Receipt | None: ...

    async def list_receipts(self, household_id: UUID, *, limit: int = 20) -> list[Receipt]: ...

    async def claim_receipt(
        self, receipt_id: UUID, household_id: UUID, *, stale_after_seconds: int
    ) -> Receipt | None:
        """Atomically move a failed/processing receipt into processing.

        Returns None when another request already holds a fresh lock.
        """
        ...

    async def update_receipt(
        self, receipt_id: UUID, household_id: UUID, fields: dict[str, object]
    ) -> Receipt: ...

    async def delete_receipt(self, receipt_id: UUID, household_id: UUID) -> None: ...

    async def list_receipt_tags(self, receipt_id: UUID) -> list[ReceiptTag]: ...

    async def list_tags(self, household_id: UUID) -> list[Tag]: ...

    async def find_tag_by_slug(self, household_id: UUID, slug: str) -> Tag | None: ...

    async def create_tag(
        self,
        *,
        household_id: UUID,
        slug: str,
        label_en: str,
        kind: str,
        keywords: list[str] | None = None,
    ) -> Tag: ...

    async def upsert_receipt_tag(
        self,
        *,
        receipt_id: UUID,
        tag_id: UUID,
        source: str,
        confidence: float | None = None,
        user_id: UUID | None = None,
    ) -> None:
        """Add or clear the soft-delete flag on a receipt tag."""
        ...

    async def remove_receipt_tag(
        self, *, receipt_id: UUID, tag_id: UUID, user_id: UUID | None = None
    ) -> None: ...

    async def find_similar_merchant_tag(
        self, household_id: UUID, merchant: str, *, threshold: float = 0.6
    ) -> Tag | None: ...
