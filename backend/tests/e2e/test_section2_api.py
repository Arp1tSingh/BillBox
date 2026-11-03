from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app
from tests.e2e.conftest import UserFactory, auth

pytestmark = pytest.mark.e2e

FIXTURES = Path(__file__).resolve().parents[3] / "frontend" / "e2e" / "fixtures"


@pytest_asyncio.fixture
async def receipt_client(live_settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=live_settings.model_copy(update={"gemini_mock": True}))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", timeout=30) as client:
        yield client


async def make_household(client: AsyncClient, token: str) -> dict:
    response = await client.post(
        "/households", json={"name": "Section 2 API home"}, headers=auth_token(token)
    )
    assert response.status_code == 201, response.text
    return response.json()


def auth_token(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_upload_process_and_delete(
    receipt_client: AsyncClient, make_user: UserFactory
) -> None:
    from tests.e2e.conftest import auth as token_auth

    owner = await make_user("s2-owner")
    household = await make_household(receipt_client, owner.token)
    image = (FIXTURES / "bill-en.png").read_bytes()

    upload = await receipt_client.post(
        "/receipts",
        files=[("files[]", ("bill.png", image, "image/png"))],
        data={"skip_ai": "false"},
        headers=token_auth(owner),
    )
    assert upload.status_code == 202, upload.text
    receipt_id = upload.json()["id"]

    detail = await receipt_client.get(f"/receipts/{receipt_id}", headers=token_auth(owner))
    assert detail.status_code == 200, detail.text
    assert len(detail.json()["pages"]) == 1
    assert detail.json()["pages"][0]["url"].startswith("http")

    processed = await receipt_client.post(
        f"/receipts/{receipt_id}/process", headers=token_auth(owner)
    )
    assert processed.status_code == 200, processed.text
    body = processed.json()
    assert body["status"] == "ready"
    assert body["merchant"] == "Demo Store"
    assert any(tag["source"] == "rule" for tag in body["tags"])

    listed = await receipt_client.get("/receipts", headers=token_auth(owner))
    assert [row["id"] for row in listed.json()] == [receipt_id]

    deleted = await receipt_client.delete(f"/receipts/{receipt_id}", headers=token_auth(owner))
    assert deleted.status_code == 204
    missing = await receipt_client.get(f"/receipts/{receipt_id}", headers=token_auth(owner))
    assert missing.status_code == 404
    assert household["id"]


async def test_pdf_upload(receipt_client: AsyncClient, make_user: UserFactory) -> None:
    owner = await make_user("s2-pdf")
    await make_household(receipt_client, owner.token)
    pdf = (FIXTURES / "bill.pdf").read_bytes()

    upload = await receipt_client.post(
        "/receipts",
        files=[("files[]", ("bill.pdf", pdf, "application/pdf"))],
        data={"skip_ai": "true"},
        headers=auth(owner),
    )
    assert upload.status_code == 202, upload.text
    detail = await receipt_client.get(f"/receipts/{upload.json()['id']}", headers=auth(owner))
    assert detail.status_code == 200
    pages = detail.json()["pages"]
    assert len(pages) == 1
    assert pages[0]["mime_type"] == "application/pdf"


async def test_rejects_text_and_skip_ai_tags(
    receipt_client: AsyncClient, make_user: UserFactory
) -> None:
    owner = await make_user("s2-validation")
    await make_household(receipt_client, owner.token)

    bad = await receipt_client.post(
        "/receipts",
        files=[("files[]", ("notes.txt", b"not a bill", "text/plain"))],
        headers=auth(owner),
    )
    assert bad.status_code == 422
    assert bad.json()["error"]["code"] == "unsupported_file_type"

    image = (FIXTURES / "bill-en.png").read_bytes()
    upload = await receipt_client.post(
        "/receipts",
        files=[("files[]", ("bill.png", image, "image/png"))],
        data={"skip_ai": "true"},
        headers=auth(owner),
    )
    assert upload.status_code == 202
    receipt_id = upload.json()["id"]
    assert upload.json()["status"] == "ready"

    detail = (
        await receipt_client.get(f"/receipts/{receipt_id}", headers=auth(owner))
    ).json()
    assert detail["ai_skipped"] is True
    assert detail["tags"] == []

    tagged = await receipt_client.post(
        f"/receipts/{receipt_id}/tags",
        json={"label": "Warranty"},
        headers=auth(owner),
    )
    assert tagged.status_code == 200
    assert any(tag["source"] == "user" for tag in tagged.json()["tags"])


async def test_outsider_cannot_read(
    receipt_client: AsyncClient, make_user: UserFactory
) -> None:
    owner = await make_user("s2-read-owner")
    outsider = await make_user("s2-read-outsider")
    await make_household(receipt_client, owner.token)
    image = (FIXTURES / "bill-en.png").read_bytes()
    upload = await receipt_client.post(
        "/receipts",
        files=[("files[]", ("bill.png", image, "image/png"))],
        data={"skip_ai": "true"},
        headers=auth(owner),
    )
    receipt_id = upload.json()["id"]

    response = await receipt_client.get(f"/receipts/{receipt_id}", headers=auth(outsider))
    assert response.status_code == 404
