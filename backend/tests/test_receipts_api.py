from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from typing import Any

from httpx import AsyncClient

from app.config import Settings
from app.domain import ExtractionResult
from app.services.extraction import ExtractionError
from tests.conftest import auth
from tests.fakes import FakeReceiptsRepository, FakeStorage, ScriptedExtractionProvider
from tests.test_households_api import create_household, join_household

JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00" + b"0" * 200
PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 200


def pdf_bytes(pages: int = 1) -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    for _ in range(pages):
        writer.add_blank_page(200, 200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


async def upload(
    client: AsyncClient,
    token: str = "owner",
    *,
    files: list[tuple[str, bytes, str]] | None = None,
    skip_ai: bool = False,
    household_id: str | None = None,
) -> Any:
    payload = files or [("bill.jpg", JPEG, "image/jpeg")]
    headers = auth(token)
    if household_id:
        headers["X-Household-Id"] = household_id
    return await client.post(
        "/receipts",
        files=[("files[]", item) for item in payload],
        data={"skip_ai": "true" if skip_ai else "false"},
        headers=headers,
    )


async def create_receipt(client: AsyncClient, **kwargs: Any) -> dict[str, Any]:
    response = await upload(client, **kwargs)
    assert response.status_code == 202, response.text
    return response.json()


async def test_upload_requires_household(client: AsyncClient) -> None:
    response = await upload(client, "outsider")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "no_household"


async def test_upload_and_fetch_detail(client: AsyncClient) -> None:
    await create_household(client)
    created = await create_receipt(client)
    assert created["status"] == "processing"

    response = await client.get(f"/receipts/{created['id']}", headers=auth("owner"))
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "processing"
    assert len(detail["pages"]) == 1
    assert detail["pages"][0]["mime_type"] == "image/jpeg"
    assert detail["pages"][0]["url"].startswith("https://storage.test/")


async def test_multi_page_upload(client: AsyncClient) -> None:
    await create_household(client)
    created = await create_receipt(
        client,
        files=[
            ("a.jpg", JPEG, "image/jpeg"),
            ("b.png", PNG, "image/png"),
        ],
    )
    detail = (
        await client.get(f"/receipts/{created['id']}", headers=auth("owner"))
    ).json()
    assert [page["page_no"] for page in detail["pages"]] == [1, 2]


async def test_pdf_upload_is_one_page_row(client: AsyncClient) -> None:
    await create_household(client)
    created = await create_receipt(
        client, files=[("bill.pdf", pdf_bytes(3), "application/pdf")]
    )
    detail = (
        await client.get(f"/receipts/{created['id']}", headers=auth("owner"))
    ).json()
    assert len(detail["pages"]) == 1
    assert detail["pages"][0]["mime_type"] == "application/pdf"


async def test_rejects_unsupported_file(client: AsyncClient) -> None:
    await create_household(client)
    response = await upload(
        client, files=[("notes.txt", b"hello world", "text/plain")]
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsupported_file_type"


async def test_rejects_too_many_pages(client: AsyncClient) -> None:
    await create_household(client)
    files = [(f"{index}.jpg", JPEG, "image/jpeg") for index in range(11)]
    response = await upload(client, files=files)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "too_many_pages"


async def test_rejects_large_upload(
    client: AsyncClient, settings: Settings
) -> None:
    await create_household(client)
    settings.max_upload_mb = 1
    big = JPEG + b"0" * (2 * 1024 * 1024)
    response = await upload(client, files=[("big.jpg", big, "image/jpeg")])
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "upload_too_large"


async def test_process_populates_fields_and_tags(
    client: AsyncClient,
) -> None:
    await create_household(client)
    created = await create_receipt(client)

    response = await client.post(f"/receipts/{created['id']}/process", headers=auth("owner"))
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["status"] == "ready"
    assert detail["merchant"] == "Adani Electricity Pvt Ltd"
    assert Decimal(detail["amount"]) == Decimal("2480.50")
    assert detail["bill_date"] == "2026-01-12"
    assert detail["title"].startswith("Adani Electricity Pvt Ltd")
    assert detail["processed_at"] is not None

    labels = {(tag["label_en"], tag["source"]) for tag in detail["tags"]}
    assert ("Electricity", "rule") in labels
    assert any(source == "ai" for _, source in labels)


async def test_process_is_idempotent(
    client: AsyncClient, extraction: ScriptedExtractionProvider
) -> None:
    await create_household(client)
    created = await create_receipt(client)
    first = await client.post(f"/receipts/{created['id']}/process", headers=auth("owner"))
    assert first.status_code == 200
    second = await client.post(f"/receipts/{created['id']}/process", headers=auth("owner"))
    assert second.status_code == 200
    assert second.json()["status"] == "ready"
    assert extraction.calls == 1


async def test_fresh_processing_lock_is_not_claimed(
    client: AsyncClient,
    receipts_repo: FakeReceiptsRepository,
    extraction: ScriptedExtractionProvider,
) -> None:
    household = await create_household(client)
    created = await create_receipt(client)
    from uuid import UUID

    receipt = receipts_repo.receipts[UUID(created["id"])]
    from dataclasses import replace

    receipts_repo.receipts[receipt.id] = replace(
        receipt, processing_started_at=datetime.now(UTC)
    )
    response = await client.post(f"/receipts/{created['id']}/process", headers=auth("owner"))
    assert response.status_code == 200
    assert response.json()["status"] == "processing"
    assert extraction.calls == 0

    receipts_repo.receipts[receipt.id] = replace(
        receipt,
        processing_started_at=datetime.now(UTC) - timedelta(minutes=6),
    )
    resumed = await client.post(f"/receipts/{created['id']}/process", headers=auth("owner"))
    assert resumed.json()["status"] == "ready"
    assert extraction.calls == 1
    assert household["id"]


async def test_failure_then_retry(
    client: AsyncClient, extraction: ScriptedExtractionProvider
) -> None:
    await create_household(client)
    created = await create_receipt(client)
    extraction.error = ExtractionError("AI quota reached")

    failed = await client.post(f"/receipts/{created['id']}/process", headers=auth("owner"))
    assert failed.status_code == 200
    body = failed.json()
    assert body["status"] == "failed"
    assert body["failure_reason"] == "AI quota reached"
    assert body["pages"], "pages stay intact for retry"

    extraction.error = None
    extraction.result = ExtractionResult(
        bill_type="water",
        merchant="Municipal Water",
        amount=Decimal("320.00"),
        currency="INR",
        bill_date=None,
        language="en",
        raw_text="water bill",
        tags=[],
    )
    retried = await client.post(f"/receipts/{created['id']}/process", headers=auth("owner"))
    assert retried.json()["status"] == "ready"
    assert retried.json()["merchant"] == "Municipal Water"


async def test_skip_ai_path_and_manual_tag(client: AsyncClient) -> None:
    await create_household(client)
    created = await create_receipt(client, skip_ai=True)
    assert created["status"] == "ready"

    detail = (
        await client.get(f"/receipts/{created['id']}", headers=auth("owner"))
    ).json()
    assert detail["ai_skipped"] is True
    assert detail["tags"] == []

    tagged = await client.post(
        f"/receipts/{created['id']}/tags",
        json={"label": "Home office"},
        headers=auth("owner"),
    )
    assert tagged.status_code == 200, tagged.text
    assert any(tag["source"] == "user" for tag in tagged.json()["tags"])


async def test_remove_then_readd_tag_is_user_sourced(
    client: AsyncClient,
) -> None:
    await create_household(client)
    created = await create_receipt(client, skip_ai=True)
    added = await client.post(
        f"/receipts/{created['id']}/tags",
        json={"label": "Warranty"},
        headers=auth("owner"),
    )
    tag = added.json()["tags"][0]

    removed = await client.delete(
        f"/receipts/{created['id']}/tags/{tag['tag_id']}", headers=auth("owner")
    )
    assert removed.status_code == 200
    assert removed.json()["tags"] == []

    readded = await client.post(
        f"/receipts/{created['id']}/tags",
        json={"tag_id": tag["tag_id"]},
        headers=auth("owner"),
    )
    assert readded.json()["tags"][0]["source"] == "user"


async def test_patch_fields_and_delete(
    client: AsyncClient, storage: FakeStorage
) -> None:
    await create_household(client)
    created = await create_receipt(client)
    response = await client.patch(
        f"/receipts/{created['id']}",
        json={"title": "January power", "merchant": "Adani", "amount": "2500.00"},
        headers=auth("owner"),
    )
    assert response.status_code == 200
    assert response.json()["title"] == "January power"
    assert Decimal(response.json()["amount"]) == Decimal("2500.00")

    deleted = await client.delete(f"/receipts/{created['id']}", headers=auth("owner"))
    assert deleted.status_code == 204
    missing = await client.get(f"/receipts/{created['id']}", headers=auth("owner"))
    assert missing.status_code == 404
    assert storage.objects == {}


async def test_outsider_cannot_read_or_process(client: AsyncClient) -> None:
    await create_household(client)
    created = await create_receipt(client)
    outsider = await upload(
        client,
        "outsider",
        household_id=created["id"],
    )
    assert outsider.status_code == 403

    read = await client.get(
        f"/receipts/{created['id']}",
        headers={**auth("outsider"), "X-Household-Id": created["id"]},
    )
    assert read.status_code == 403


async def test_failed_upload_cleans_up(
    client: AsyncClient,
    receipts_repo: FakeReceiptsRepository,
    storage: FakeStorage,
) -> None:
    await create_household(client)
    storage.fail_upload = True
    response = await upload(client)
    assert response.status_code == 502
    assert receipts_repo.receipts == {}
    assert receipts_repo.pages == {}
    assert storage.objects == {}


async def test_list_is_newest_first_and_household_scoped(client: AsyncClient) -> None:
    household = await create_household(client)
    first = await create_receipt(client)
    second = await create_receipt(client)

    listed = await client.get("/receipts", headers=auth("owner"))
    assert listed.status_code == 200
    ids = [row["id"] for row in listed.json()]
    assert ids == [second["id"], first["id"]]
    assert listed.json()[0]["thumbnail_url"]

    await join_household(client, household["invite_code"], "member")
    member_list = await client.get("/receipts", headers=auth("member"))
    assert {row["id"] for row in member_list.json()} == set(ids)


async def test_add_second_bill_type_replaces_first(client: AsyncClient) -> None:
    await create_household(client)
    created = await create_receipt(client)
    await client.post(f"/receipts/{created['id']}/process", headers=auth("owner"))
    detail = (
        await client.get(f"/receipts/{created['id']}", headers=auth("owner"))
    ).json()
    electricity = next(tag for tag in detail["tags"] if tag["slug"] == "electricity")

    tags = (await client.get("/receipts", headers=auth("owner"))).json()
    assert tags
    # Add a household custom tag, then a system bill type: bill type stays unique.
    response = await client.post(
        f"/receipts/{created['id']}/tags",
        json={"tag_id": electricity["tag_id"]},
        headers=auth("owner"),
    )
    bill_types = [tag for tag in response.json()["tags"] if tag["kind"] == "bill_type"]
    assert len(bill_types) == 1
    assert bill_types[0]["source"] == "user"
