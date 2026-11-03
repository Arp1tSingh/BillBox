"""In-memory household repository for fast API tests."""

from __future__ import annotations

import difflib
from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from app.domain import (
    ExtractionResult,
    Household,
    MemberRecord,
    Membership,
    Receipt,
    ReceiptPage,
    ReceiptTag,
    Tag,
)
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


class FakeReceiptsRepository:
    """In-memory receipts, pages and tags with the same soft-delete rules."""

    def __init__(self) -> None:
        self.receipts: dict[UUID, Receipt] = {}
        self.pages: dict[UUID, list[ReceiptPage]] = {}
        self.tags: dict[UUID, Tag] = {}
        self.receipt_tags: dict[tuple[UUID, UUID], dict[str, object]] = {}
        self._seed_system_tags()

    def _seed_system_tags(self) -> None:
        seed = {
            "electricity": ("Electricity", ["electricity", "MSEDCL", "बिजली", "वीज"]),
            "water": ("Water", ["water", "पानी", "पाणी"]),
            "groceries": ("Groceries", ["grocery", "kirana", "किराना", "किराणा"]),
            "dining": ("Dining", ["restaurant", "cafe", "dining", "hotel"]),
        }
        for slug, (label, keywords) in seed.items():
            tag = Tag(
                id=uuid4(),
                household_id=None,
                slug=slug,
                label_en=label,
                label_hi=None,
                label_mr=None,
                kind="bill_type",
                keywords=keywords,
            )
            self.tags[tag.id] = tag

    async def create_receipt(
        self,
        *,
        household_id: UUID,
        created_by: UUID,
        status: str = "processing",
        ai_skipped: bool = False,
        extracted: dict[str, object] | None = None,
        processed_at: object | None = None,
    ) -> Receipt:
        now = datetime.now(UTC)
        receipt = Receipt(
            id=uuid4(),
            household_id=household_id,
            created_by=created_by,
            title=None,
            merchant=None,
            amount=None,
            currency="INR",
            bill_date=None,
            bill_type=None,
            language=None,
            status=status,  # type: ignore[arg-type]
            raw_text=None,
            extracted=extracted,
            ai_skipped=ai_skipped,
            failure_reason=None,
            processing_started_at=None,
            processed_at=processed_at,  # type: ignore[arg-type]
            created_at=now,
            updated_at=now,
        )
        self.receipts[receipt.id] = receipt
        self.pages[receipt.id] = []
        return receipt

    async def add_page(
        self,
        *,
        receipt_id: UUID,
        page_no: int,
        storage_path: str,
        mime_type: str,
        size_bytes: int,
    ) -> ReceiptPage:
        page = ReceiptPage(
            id=uuid4(),
            receipt_id=receipt_id,
            page_no=page_no,
            storage_path=storage_path,
            mime_type=mime_type,
            size_bytes=size_bytes,
        )
        self.pages.setdefault(receipt_id, []).append(page)
        return page

    async def list_pages(self, receipt_id: UUID) -> list[ReceiptPage]:
        return sorted(self.pages.get(receipt_id, []), key=lambda page: page.page_no)

    async def get_receipt(self, receipt_id: UUID, household_id: UUID) -> Receipt | None:
        receipt = self.receipts.get(receipt_id)
        if receipt is None or receipt.household_id != household_id:
            return None
        return receipt

    async def list_receipts(self, household_id: UUID, *, limit: int = 20) -> list[Receipt]:
        rows = [r for r in self.receipts.values() if r.household_id == household_id]
        rows.sort(key=lambda receipt: receipt.created_at, reverse=True)
        return rows[:limit]

    async def claim_receipt(
        self, receipt_id: UUID, household_id: UUID, *, stale_after_seconds: int
    ) -> Receipt | None:
        receipt = self.receipts.get(receipt_id)
        if receipt is None or receipt.household_id != household_id:
            return None
        if receipt.status not in ("failed", "processing"):
            return None
        now = datetime.now(UTC)
        if (
            receipt.processing_started_at is not None
            and (now - receipt.processing_started_at).total_seconds() < stale_after_seconds
        ):
            return None
        updated = replace(
            receipt,
            status="processing",
            processing_started_at=now,
            failure_reason=None,
            updated_at=now,
        )
        self.receipts[receipt_id] = updated
        return updated

    async def update_receipt(
        self, receipt_id: UUID, household_id: UUID, fields: dict[str, object]
    ) -> Receipt:
        receipt = self.receipts[receipt_id]
        if receipt.household_id != household_id:
            raise KeyError("Receipt not found")
        converted: dict[str, object] = {}
        for key, value in fields.items():
            if key == "bill_date" and isinstance(value, str):
                converted[key] = date.fromisoformat(value)
            elif key == "amount" and isinstance(value, str):
                converted[key] = Decimal(value)
            elif key in ("processed_at", "processing_started_at") and isinstance(value, str):
                converted[key] = datetime.fromisoformat(value)
            else:
                converted[key] = value
        updated = replace(receipt, **converted, updated_at=datetime.now(UTC))
        self.receipts[receipt_id] = updated
        return updated

    async def delete_receipt(self, receipt_id: UUID, household_id: UUID) -> None:
        receipt = self.receipts.get(receipt_id)
        if receipt is not None and receipt.household_id == household_id:
            self.receipts.pop(receipt_id, None)
            self.pages.pop(receipt_id, None)
            for key in [key for key in self.receipt_tags if key[0] == receipt_id]:
                self.receipt_tags.pop(key, None)

    async def list_receipt_tags(self, receipt_id: UUID) -> list[ReceiptTag]:
        rows: list[ReceiptTag] = []
        for (row_receipt_id, tag_id), value in self.receipt_tags.items():
            if row_receipt_id != receipt_id:
                continue
            tag = self.tags.get(tag_id)
            if tag is None:
                continue
            rows.append(
                ReceiptTag(
                    tag=tag,
                    source=value["source"],  # type: ignore[arg-type]
                    confidence=value.get("confidence"),  # type: ignore[arg-type]
                    removed_at=value.get("removed_at"),  # type: ignore[arg-type]
                )
            )
        return rows

    async def list_tags(self, household_id: UUID) -> list[Tag]:
        return [
            tag
            for tag in self.tags.values()
            if tag.household_id is None or tag.household_id == household_id
        ]

    async def find_tag_by_slug(self, household_id: UUID, slug: str) -> Tag | None:
        return next(
            (
                tag
                for tag in self.tags.values()
                if tag.slug == slug and tag.household_id in (None, household_id)
            ),
            None,
        )

    async def create_tag(
        self,
        *,
        household_id: UUID,
        slug: str,
        label_en: str,
        kind: str,
        keywords: list[str] | None = None,
    ) -> Tag:
        existing = next(
            (
                tag
                for tag in self.tags.values()
                if tag.household_id == household_id and tag.slug == slug
            ),
            None,
        )
        if existing is not None:
            return existing
        tag = Tag(
            id=uuid4(),
            household_id=household_id,
            slug=slug,
            label_en=label_en,
            label_hi=None,
            label_mr=None,
            kind=kind,  # type: ignore[arg-type]
            keywords=keywords or [],
        )
        self.tags[tag.id] = tag
        return tag

    async def upsert_receipt_tag(
        self,
        *,
        receipt_id: UUID,
        tag_id: UUID,
        source: str,
        confidence: float | None = None,
        user_id: UUID | None = None,
    ) -> None:
        self.receipt_tags[(receipt_id, tag_id)] = {
            "source": source,
            "confidence": confidence,
            "removed_at": None,
            "removed_by": user_id,
        }

    async def remove_receipt_tag(
        self, *, receipt_id: UUID, tag_id: UUID, user_id: UUID | None = None
    ) -> None:
        key = (receipt_id, tag_id)
        if key in self.receipt_tags:
            self.receipt_tags[key]["removed_at"] = datetime.now(UTC)
            self.receipt_tags[key]["removed_by"] = user_id

    async def tag_counts(self, household_id: UUID) -> dict[UUID, int]:
        counts: dict[UUID, int] = {}
        household_receipts = {
            receipt_id
            for receipt_id, receipt in self.receipts.items()
            if receipt.household_id == household_id
        }
        for (receipt_id, tag_id), value in self.receipt_tags.items():
            if receipt_id in household_receipts and value.get("removed_at") is None:
                counts[tag_id] = counts.get(tag_id, 0) + 1
        return counts

    async def find_similar_merchant_tag(
        self, household_id: UUID, merchant: str, *, threshold: float = 0.6
    ) -> Tag | None:
        target = merchant.casefold()
        best: tuple[float, Tag] | None = None
        for tag in self.tags.values():
            if tag.household_id != household_id or tag.kind != "merchant":
                continue
            ratio = difflib.SequenceMatcher(None, target, tag.label_en.casefold()).ratio()
            if ratio > threshold and (best is None or ratio > best[0]):
                best = (ratio, tag)
        return best[1] if best else None


    async def search_receipts(
        self,
        household_id: UUID,
        *,
        query: str | None = None,
        tag_ids: list[UUID] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        sort: str = "date",
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[Receipt], int]:
        tags_by_receipt: dict[UUID, set[UUID]] = {}
        for (receipt_id, tag_id), value in self.receipt_tags.items():
            if value.get("removed_at") is None:
                tags_by_receipt.setdefault(receipt_id, set()).add(tag_id)

        async def searchable(receipt: Receipt) -> str:
            parts = [receipt.title, receipt.merchant, receipt.raw_text, receipt.bill_type]
            for tag_id in tags_by_receipt.get(receipt.id, set()):
                tag = self.tags.get(tag_id)
                if tag:
                    parts.extend([tag.label_en, tag.label_hi, tag.label_mr])
            return " ".join(part for part in parts if part).casefold()

        selected = set(tag_ids or [])
        terms = [term for term in (query or "").casefold().split() if term]
        matches: list[tuple[int, Receipt]] = []
        for receipt in self.receipts.values():
            if receipt.household_id != household_id:
                continue
            if date_from is not None and (
                receipt.bill_date is None or receipt.bill_date < date_from
            ):
                continue
            if date_to is not None and (receipt.bill_date is None or receipt.bill_date > date_to):
                continue
            if min_amount is not None and (receipt.amount is None or receipt.amount < min_amount):
                continue
            if max_amount is not None and (receipt.amount is None or receipt.amount > max_amount):
                continue
            present = tags_by_receipt.get(receipt.id, set())
            tag_hits = len(present & selected)
            if selected and tag_hits != len(selected):
                continue
            text = await searchable(receipt)
            fts_hit = bool(terms) and all(term in text for term in terms)
            merchant_hit = bool(
                query
                and receipt.merchant
                and difflib.SequenceMatcher(
                    None, query.casefold(), receipt.merchant.casefold()
                ).ratio()
                > 0.5
            )
            if terms and not (fts_hit or merchant_hit or tag_hits):
                continue
            relevance = 3 if tag_hits else 2 if merchant_hit else 1 if fts_hit else 0
            matches.append((relevance, receipt))

        def sort_key(item: tuple[int, Receipt]) -> tuple:
            relevance, receipt = item
            date_key = receipt.bill_date.toordinal() if receipt.bill_date else -1
            amount_key = float(receipt.amount) if receipt.amount is not None else -1.0
            if sort == "amount":
                return (-amount_key, -date_key, -receipt.created_at.timestamp())
            if sort == "relevance":
                return (-relevance, -date_key, -receipt.created_at.timestamp())
            return (-date_key, -receipt.created_at.timestamp())

        matches.sort(key=sort_key)
        total = len(matches)
        page = [receipt for _, receipt in matches[offset : offset + limit]]
        return page, total
class FakeStorage:
    def __init__(self) -> None:
        self.objects: dict[str, tuple[bytes, str]] = {}
        self.fail_upload = False

    async def upload(self, path: str, data: bytes, content_type: str) -> None:
        if self.fail_upload:
            raise RuntimeError("storage unavailable")
        self.objects[path] = (data, content_type)

    async def download(self, path: str) -> bytes:
        return self.objects[path][0]

    async def signed_url(self, path: str, *, expires_in: int = 3600) -> str:
        return f"https://storage.test/{path}?expires={expires_in}"

    async def delete(self, paths: list[str]) -> None:
        for path in paths:
            self.objects.pop(path, None)


class ScriptedExtractionProvider:
    def __init__(self, result: ExtractionResult | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls = 0
        self.page_counts: list[int] = []

    async def extract(self, pages: list[tuple[bytes, str]]) -> ExtractionResult:
        self.calls += 1
        self.page_counts.append(len(pages))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result

