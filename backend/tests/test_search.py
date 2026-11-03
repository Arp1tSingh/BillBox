from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from httpx import AsyncClient

from app.domain import Receipt, Tag
from app.services.search import SearchParser, resolve_tag_filters
from tests.conftest import auth
from tests.fakes import FakeReceiptsRepository
from tests.test_households_api import create_household


def seeded_tags(repo: FakeReceiptsRepository) -> dict[str, Tag]:
    return {tag.slug: tag for tag in repo.tags.values()}


def test_parse_amount_phrases() -> None:
    tags: list[Tag] = []
    assert SearchParser(tags).parse("over 5000").min_amount == Decimal("5000.00")
    assert SearchParser(tags).parse("more than 1,200").min_amount == Decimal("1200.00")
    assert SearchParser(tags).parse("under 1000").max_amount == Decimal("1000.00")
    parsed = SearchParser(tags).parse("between 1000 and 5000")
    assert (parsed.min_amount, parsed.max_amount) == (Decimal("1000.00"), Decimal("5000.00"))
    assert SearchParser(tags).parse("less than ₹300").max_amount == Decimal("300.00")


def test_parse_dates_relative_and_absolute() -> None:
    parser = SearchParser([], today=date(2026, 11, 3))
    last = parser.parse("last month")
    assert (last.date_from, last.date_to) == (date(2026, 10, 1), date(2026, 10, 31))
    this = parser.parse("this month")
    assert (this.date_from, this.date_to) == (date(2026, 11, 1), date(2026, 11, 30))
    year = parser.parse("2025")
    assert (year.date_from, year.date_to) == (date(2025, 1, 1), date(2025, 12, 31))
    month = parser.parse("Jan 2025")
    assert (month.date_from, month.date_to) == (date(2025, 1, 1), date(2025, 1, 31))
    assert month.text is None


def test_parse_tags_in_three_scripts() -> None:
    repo = FakeReceiptsRepository()
    tags = list(repo.tags.values())
    parser = SearchParser(tags)
    electricity = next(tag for tag in tags if tag.slug == "electricity")
    water = next(tag for tag in tags if tag.slug == "water")

    assert parser.parse("electricity").tag_ids == [electricity.id]
    assert parser.parse("बिजली").tag_ids == [electricity.id]
    assert parser.parse("पाणी").tag_ids == [water.id]
    parsed = parser.parse("electricity bill")
    assert parsed.tag_ids == [electricity.id]
    assert parsed.text == "bill"


def test_resolve_explicit_tag_filters() -> None:
    repo = FakeReceiptsRepository()
    tags = list(repo.tags.values())
    water = next(tag for tag in tags if tag.slug == "water")
    ids = resolve_tag_filters(["water", "पाणी", str(water.id), "nope"], tags)
    assert ids == [water.id]


def seed_receipt(
    repo: FakeReceiptsRepository,
    household_id: UUID,
    *,
    title: str,
    merchant: str,
    amount: str,
    bill_date: date,
    raw_text: str,
    tag_slug: str | None = None,
) -> Receipt:
    now = datetime.now(UTC)
    receipt = Receipt(
        id=__import__("uuid").uuid4(),
        household_id=household_id,
        created_by=None,
        title=title,
        merchant=merchant,
        amount=Decimal(amount),
        currency="INR",
        bill_date=bill_date,
        bill_type=tag_slug,
        language="en",
        status="ready",
        raw_text=raw_text,
        extracted=None,
        ai_skipped=False,
        failure_reason=None,
        processing_started_at=None,
        processed_at=now,
        created_at=now,
        updated_at=now,
    )
    repo.receipts[receipt.id] = receipt
    repo.pages[receipt.id] = []
    if tag_slug:
        tag = seeded_tags(repo)[tag_slug]
        repo.receipt_tags[(receipt.id, tag.id)] = {
            "source": "rule",
            "confidence": 1.0,
            "removed_at": None,
            "removed_by": None,
        }
    return receipt


async def test_search_ranks_and_filters(
    client: AsyncClient, receipts_repo: FakeReceiptsRepository
) -> None:
    household = await create_household(client)
    household_id = UUID(household["id"])
    seed_receipt(
        receipts_repo,
        household_id,
        title="December power",
        merchant="Adani Electricity",
        amount="6000.00",
        bill_date=date(2025, 12, 10),
        raw_text="electricity bill",
        tag_slug="electricity",
    )
    seed_receipt(
        receipts_repo,
        household_id,
        title="Monthly kirana",
        merchant="Kirana Store",
        amount="900.00",
        bill_date=date(2026, 1, 5),
        raw_text="grocery bill",
        tag_slug="groceries",
    )
    seed_receipt(
        receipts_repo,
        household_id,
        title="February power",
        merchant="Adani Electricity",
        amount="2000.00",
        bill_date=date(2026, 2, 1),
        raw_text="electricity bill",
    )

    response = await client.get(
        "/receipts", params={"q": "electricity bill"}, headers=auth("owner")
    )
    body = response.json()
    assert response.status_code == 200, response.text
    assert body["total"] == 1
    assert body["items"][0]["title"] == "December power"

    hindi = (
        await client.get("/receipts", params={"q": "बिजली"}, headers=auth("owner"))
    ).json()
    assert [item["title"] for item in hindi["items"]] == ["December power"]

    over = (
        await client.get("/receipts", params={"q": "over 5000"}, headers=auth("owner"))
    ).json()
    assert [item["title"] for item in over["items"]] == ["December power"]

    under = (
        await client.get("/receipts", params={"q": "under 1000"}, headers=auth("owner"))
    ).json()
    assert [item["title"] for item in under["items"]] == ["Monthly kirana"]

    between = (
        await client.get(
            "/receipts", params={"q": "between 1000 and 5000"}, headers=auth("owner")
        )
    ).json()
    assert [item["title"] for item in between["items"]] == ["February power"]

    fuzzy = (
        await client.get("/receipts", params={"q": "Adani Elec"}, headers=auth("owner"))
    ).json()
    assert fuzzy["total"] == 2


async def test_search_tag_chips_sort_and_pagination(
    client: AsyncClient, receipts_repo: FakeReceiptsRepository
) -> None:
    household = await create_household(client)
    household_id = UUID(household["id"])
    for index in range(3):
        seed_receipt(
            receipts_repo,
            household_id,
            title=f"Power {index}",
            merchant="Adani Electricity",
            amount=str(1000 + index * 100),
            bill_date=date(2026, 1, 1 + index),
            raw_text="electricity bill",
            tag_slug="electricity",
        )
    seed_receipt(
        receipts_repo,
        household_id,
        title="Kirana",
        merchant="Kirana Store",
        amount="5000.00",
        bill_date=date(2026, 1, 20),
        raw_text="grocery",
        tag_slug="groceries",
    )

    both = (
        await client.get(
            "/receipts",
            params=[("tag", "electricity"), ("tag", "groceries")],
            headers=auth("owner"),
        )
    ).json()
    assert both["total"] == 0

    sorted_amount = (
        await client.get("/receipts", params={"sort": "amount"}, headers=auth("owner"))
    ).json()
    assert sorted_amount["items"][0]["title"] == "Kirana"

    page = (
        await client.get(
            "/receipts", params={"page": 2, "page_size": 2}, headers=auth("owner")
        )
    ).json()
    assert page["total"] == 4
    assert len(page["items"]) == 2

    explicit_dates = (
        await client.get(
            "/receipts", params={"from": "2026-01-02", "to": "2026-01-03"}, headers=auth("owner")
        )
    ).json()
    assert explicit_dates["total"] == 2


async def test_explicit_tag_combines_with_tag_in_query(
    client: AsyncClient, receipts_repo: FakeReceiptsRepository
) -> None:
    household = await create_household(client)
    household_id = UUID(household["id"])
    both = seed_receipt(
        receipts_repo,
        household_id,
        title="Power and kirana",
        merchant="Adani Electricity",
        amount="2500.00",
        bill_date=date(2026, 2, 10),
        raw_text="electricity bill grocery",
        tag_slug="electricity",
    )
    groceries = seeded_tags(receipts_repo)["groceries"]
    receipts_repo.receipt_tags[(both.id, groceries.id)] = {
        "source": "rule",
        "confidence": 1.0,
        "removed_at": None,
        "removed_by": None,
    }
    seed_receipt(
        receipts_repo,
        household_id,
        title="Groceries only",
        merchant="Kirana Store",
        amount="900.00",
        bill_date=date(2026, 2, 11),
        raw_text="grocery bill",
        tag_slug="groceries",
    )

    response = await client.get(
        "/receipts",
        params=[("q", "electricity"), ("tag", "groceries")],
        headers=auth("owner"),
    )
    body = response.json()
    assert response.status_code == 200, response.text
    assert [item["title"] for item in body["items"]] == ["Power and kirana"]


async def test_search_is_household_scoped(
    client: AsyncClient, receipts_repo: FakeReceiptsRepository
) -> None:
    household = await create_household(client)
    seed_receipt(
        receipts_repo,
        UUID(household["id"]),
        title="Private power",
        merchant="Adani Electricity",
        amount="6000.00",
        bill_date=date(2026, 1, 1),
        raw_text="electricity bill",
        tag_slug="electricity",
    )
    response = await client.get("/receipts", params={"q": "electricity"}, headers=auth("outsider"))
    assert response.status_code == 404


async def test_test_seed_endpoint_creates_searchable_receipt(
    client: AsyncClient, receipts_repo: FakeReceiptsRepository
) -> None:
    await create_household(client)
    response = await client.post(
        "/test/receipts",
        json={
            "title": "Seeded power bill",
            "merchant": "Adani Electricity",
            "amount": "4500.00",
            "bill_date": "2026-02-01",
            "raw_text": "बिजली बिल",
            "bill_type": "electricity",
            "tags": ["electricity"],
        },
        headers=auth("owner"),
    )
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "ready"
    assert detail["amount"] == "4500.00"
    assert [tag["slug"] for tag in detail["tags"]] == ["electricity"]

    found = await client.get("/receipts?q=बिजली", headers=auth("owner"))
    assert found.status_code == 200, found.text
    body = found.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == detail["id"]
