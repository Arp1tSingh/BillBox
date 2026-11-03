from __future__ import annotations

from dataclasses import replace
from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import uuid4

from app.domain import ExtractionResult, Receipt
from app.services.tagging import TaggingService, normalize_merchant, slugify
from tests.fakes import FakeReceiptsRepository


def make_receipt(repo: FakeReceiptsRepository) -> Receipt:
    now = datetime.now(UTC)
    receipt = Receipt(
        id=uuid4(),
        household_id=uuid4(),
        created_by=uuid4(),
        title=None,
        merchant=None,
        amount=None,
        currency="INR",
        bill_date=None,
        bill_type=None,
        language=None,
        status="processing",
        raw_text=None,
        extracted=None,
        ai_skipped=False,
        failure_reason=None,
        processing_started_at=None,
        processed_at=None,
        created_at=now,
        updated_at=now,
    )
    repo.receipts[receipt.id] = receipt
    repo.pages[receipt.id] = []
    return receipt


def result(**overrides: object) -> ExtractionResult:
    base = ExtractionResult(
        bill_type=None,
        merchant=None,
        amount=Decimal("100.00"),
        currency="INR",
        bill_date=date(2026, 1, 1),
        language="en",
        raw_text="",
        tags=[],
    )
    return replace(base, **overrides)  # type: ignore[arg-type]


def test_merchant_normalization_and_slug() -> None:
    assert normalize_merchant("Croma Pvt Ltd") == "Croma"
    assert normalize_merchant("  Adani   Electricity Limited ") == "Adani Electricity"
    assert slugify("Croma Pvt Ltd") == "croma-pvt-ltd"


async def test_rules_win_and_hindi_keywords_match() -> None:
    repo = FakeReceiptsRepository()
    receipt = make_receipt(repo)
    service = TaggingService(repo)

    bill_type = await service.apply(
        receipt,
        result(raw_text="MSEDCL electricity bill", merchant="MSEDCL"),
    )
    assert bill_type == "electricity"
    labels = {row.tag.label_en for row in await repo.list_receipt_tags(receipt.id)}
    assert "Electricity" in labels

    hindi = make_receipt(repo)
    assert await service.apply(hindi, result(raw_text="पाणी बिल", merchant="पालिका")) == "water"


async def test_ai_bill_type_used_only_when_no_rule() -> None:
    repo = FakeReceiptsRepository()
    receipt = make_receipt(repo)
    service = TaggingService(repo)

    assert await service.apply(receipt, result(raw_text="shop purchase")) is None
    assert await service.apply(
        receipt, result(raw_text="shop purchase", bill_type="groceries")
    ) == "groceries"


async def test_merchant_variants_merge() -> None:
    repo = FakeReceiptsRepository()
    service = TaggingService(repo)
    first = make_receipt(repo)
    second = make_receipt(repo)
    second = replace(second, household_id=first.household_id)

    await service.apply(first, result(merchant="Croma Pvt Ltd"))
    await service.apply(second, result(merchant="Croma"))

    merchant_tags = [tag for tag in repo.tags.values() if tag.kind == "merchant"]
    assert len(merchant_tags) == 1
    assert merchant_tags[0].label_en == "Croma"


async def test_removed_tag_is_not_restored_by_rerun() -> None:
    repo = FakeReceiptsRepository()
    receipt = make_receipt(repo)
    service = TaggingService(repo)
    await service.apply(receipt, result(raw_text="electricity bill"))

    electricity = next(tag for tag in repo.tags.values() if tag.slug == "electricity")
    await repo.remove_receipt_tag(receipt_id=receipt.id, tag_id=electricity.id, user_id=uuid4())

    await service.apply(receipt, result(raw_text="electricity bill"))
    active = [
        row
        for row in await repo.list_receipt_tags(receipt.id)
        if row.removed_at is None and row.tag.id == electricity.id
    ]
    assert active == []


async def test_second_bill_type_replaces_first() -> None:
    repo = FakeReceiptsRepository()
    receipt = make_receipt(repo)
    service = TaggingService(repo)

    await service.apply(receipt, result(raw_text="electricity bill"))
    await service.apply(receipt, result(raw_text="water bill"))
    active = [
        row.tag.slug
        for row in await repo.list_receipt_tags(receipt.id)
        if row.removed_at is None and row.tag.kind == "bill_type"
    ]
    assert active == ["water"]
