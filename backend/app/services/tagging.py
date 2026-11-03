"""Rule-first tagging, merchant normalisation and manual tag edits."""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from app.domain import ExtractionResult, Receipt, Tag
from app.repositories.base import ReceiptsRepository
from app.rules.bill_types import BILL_TYPE_LABELS, BILL_TYPE_SLUGS

_SUFFIXES = re.compile(
    r"(?i)\b(pvt\.?\s*ltd|private\s+limited|limited|ltd|llp|inc|corp|corporation)\b\.?"
)
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
_SPACES = re.compile(r"\s+")


def normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return unicodedata.normalize("NFC", value).casefold()


def normalize_merchant(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = _SUFFIXES.sub(" ", unicodedata.normalize("NFC", value))
    cleaned = _SPACES.sub(" ", cleaned).strip(" .,-")
    if not cleaned:
        return None
    return cleaned.title()


def slugify(value: str) -> str:
    slug = _NON_WORD.sub("-", normalize_text(value)).strip("-")
    return slug[:60] or "tag"


class TaggingService:
    def __init__(self, repo: ReceiptsRepository) -> None:
        self.repo = repo

    async def apply(self, receipt: Receipt, result: ExtractionResult) -> str | None:
        """Apply rule/AI tags; return the active bill-type slug."""
        tags = await self.repo.list_tags(receipt.household_id)
        states = {row.tag.id: row for row in await self.repo.list_receipt_tags(receipt.id)}
        text = normalize_text(" ".join(filter(None, [result.raw_text, result.merchant])))

        system_by_slug = {tag.slug: tag for tag in tags if tag.household_id is None}
        chosen = self._rule_bill_type(text, tags)
        source = "rule"
        if chosen is None:
            source = "ai"
            chosen = system_by_slug.get(result.bill_type or "")

        active = [row for row in states.values() if row.removed_at is None]
        active_bill_types = [row for row in active if row.tag.kind == "bill_type"]
        user_owns_bill_type = any(row.source == "user" for row in active_bill_types)

        if chosen and not user_owns_bill_type:
            for row in active_bill_types:
                if row.tag.id != chosen.id:
                    await self.repo.remove_receipt_tag(
                        receipt_id=receipt.id, tag_id=row.tag.id, user_id=None
                    )
            if chosen.id not in states:
                await self.repo.upsert_receipt_tag(
                    receipt_id=receipt.id,
                    tag_id=chosen.id,
                    source=source,
                    confidence=1.0 if source == "rule" else None,
                )
            states[chosen.id] = None  # type: ignore[assignment]

        if result.merchant:
            merchant_tag = await self._merchant_tag(receipt.household_id, result.merchant)
            if merchant_tag and merchant_tag.id not in states:
                await self.repo.upsert_receipt_tag(
                    receipt_id=receipt.id, tag_id=merchant_tag.id, source="ai"
                )
                states[merchant_tag.id] = None  # type: ignore[assignment]

        duplicate_labels = {normalize_text(tag.label_en) for tag in tags}
        bill_label = normalize_text(BILL_TYPE_LABELS.get(chosen.slug) if chosen else None)
        for label in result.tags[:3]:
            clean = label.strip()
            normal = normalize_text(clean)
            if not clean or normal == bill_label or normal in duplicate_labels:
                continue
            custom = await self._custom_tag(receipt.household_id, clean)
            if custom and custom.id not in states:
                await self.repo.upsert_receipt_tag(
                    receipt_id=receipt.id, tag_id=custom.id, source="ai"
                )
                states[custom.id] = None  # type: ignore[assignment]
            duplicate_labels.add(normal)

        final_active = [
            row.tag
            for row in await self.repo.list_receipt_tags(receipt.id)
            if row.removed_at is None and row.tag.kind == "bill_type"
        ]
        return final_active[0].slug if final_active else None

    def _rule_bill_type(self, text: str, tags: list[Tag]) -> Tag | None:
        if not text:
            return None
        order = {slug: index for index, slug in enumerate(BILL_TYPE_SLUGS)}
        candidates = [tag for tag in tags if tag.household_id is None and tag.kind == "bill_type"]
        candidates.sort(key=lambda tag: order.get(tag.slug, 999))
        for tag in candidates:
            for keyword in tag.keywords:
                needle = normalize_text(keyword)
                if needle and needle in text:
                    return tag
        return None

    async def _merchant_tag(self, household_id: UUID, merchant: str) -> Tag | None:
        normalized = normalize_merchant(merchant)
        if not normalized:
            return None
        similar = await self.repo.find_similar_merchant_tag(household_id, normalized)
        if similar is not None:
            return similar
        return await self.repo.create_tag(
            household_id=household_id,
            slug=slugify(normalized),
            label_en=normalized,
            kind="merchant",
        )

    async def _custom_tag(self, household_id: UUID, label: str) -> Tag | None:
        normalized = normalize_merchant(label) or label.strip()
        if not normalized:
            return None
        slug = slugify(normalized)
        for tag in await self.repo.list_tags(household_id):
            if tag.household_id == household_id and tag.slug == slug:
                return tag
        return await self.repo.create_tag(
            household_id=household_id,
            slug=slug,
            label_en=normalized,
            kind="custom",
        )

    async def add_user_tag(
        self,
        receipt: Receipt,
        user_id: UUID,
        *,
        tag_id: UUID | None = None,
        label: str | None = None,
    ) -> Tag:
        tags = await self.repo.list_tags(receipt.household_id)
        if tag_id is not None:
            tag = next((item for item in tags if item.id == tag_id), None)
            if tag is None:
                raise LookupError("tag_not_found")
        else:
            clean = (label or "").strip()
            if not clean:
                raise ValueError("tag_label_required")
            tag = await self._custom_tag(receipt.household_id, clean)
            if tag is None:
                raise ValueError("tag_label_required")

        if tag.kind == "bill_type":
            active = [
                row
                for row in await self.repo.list_receipt_tags(receipt.id)
                if row.removed_at is None and row.tag.kind == "bill_type"
            ]
            for row in active:
                if row.tag.id != tag.id:
                    await self.repo.remove_receipt_tag(
                        receipt_id=receipt.id, tag_id=row.tag.id, user_id=user_id
                    )

        await self.repo.upsert_receipt_tag(
            receipt_id=receipt.id, tag_id=tag.id, source="user", user_id=user_id
        )
        if tag.kind == "bill_type":
            await self.repo.update_receipt(
                receipt.id, receipt.household_id, {"bill_type": tag.slug}
            )
        return tag
