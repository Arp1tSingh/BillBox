from __future__ import annotations

import csv
import io
import zipfile

from httpx import AsyncClient

from tests.conftest import auth
from tests.fakes import FakeReceiptsRepository, FakeStorage
from tests.test_households_api import create_household
from tests.test_receipts_api import create_receipt


async def test_export_zip_contains_csv_pages_and_tags(
    client: AsyncClient,
    receipts_repo: FakeReceiptsRepository,
    storage: FakeStorage,
) -> None:
    await create_household(client)
    receipt = await create_receipt(client, skip_ai=True)
    await client.patch(
        f"/receipts/{receipt['id']}",
        json={"title": "February power", "merchant": "Adani Electricity", "amount": "4500.00"},
        headers=auth("owner"),
    )
    added = await client.post(
        f"/receipts/{receipt['id']}/tags",
        json={"label": "किराया"},
        headers=auth("owner"),
    )
    assert added.status_code == 200, added.text
    pdf = await create_receipt(
        client,
        skip_ai=True,
        files=[("bill.pdf", _pdf_bytes(), "application/pdf")],
    )

    response = await client.get("/households/export", headers=auth("owner"))
    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/zip"
    assert response.headers["content-disposition"].startswith("attachment; filename=")

    archive = zipfile.ZipFile(io.BytesIO(response.content))
    names = set(archive.namelist())
    assert "receipts.csv" in names
    assert f"pages/{receipt['id']}/1.jpg" in names
    assert f"pages/{pdf['id']}/1.pdf" in names

    rows = list(csv.DictReader(io.StringIO(archive.read("receipts.csv").decode("utf-8-sig"))))
    assert len(rows) == 2
    row = next(item for item in rows if item["Receipt ID"] == receipt["id"])
    assert row["Title"] == "February power"
    assert row["Merchant"] == "Adani Electricity"
    assert row["Amount"] == "4500.00"
    assert row["Tags"] == "किराया"
    assert row["Pages"] == "1"

    assert len(storage.objects) == 2
    assert receipts_repo.receipts


async def test_export_skips_missing_storage_objects(
    client: AsyncClient,
    receipts_repo: FakeReceiptsRepository,
    storage: FakeStorage,
) -> None:
    await create_household(client)
    receipt = await create_receipt(client, skip_ai=True)
    for page in receipts_repo.pages[next(iter(receipts_repo.pages))]:
        storage.objects.pop(page.storage_path, None)

    response = await client.get("/households/export", headers=auth("owner"))
    assert response.status_code == 200, response.text
    archive = zipfile.ZipFile(io.BytesIO(response.content))
    assert "receipts.csv" in archive.namelist()
    assert not any(name.startswith("pages/") for name in archive.namelist())
    rows = list(csv.DictReader(io.StringIO(archive.read("receipts.csv").decode("utf-8-sig"))))
    assert rows[0]["Receipt ID"] == receipt["id"]


async def test_export_requires_membership(client: AsyncClient) -> None:
    household = await create_household(client)
    await create_household(client, token="outsider", name="Other home")

    response = await client.get(
        "/households/export",
        headers={**auth("outsider"), "X-Household-Id": household["id"]},
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "not_a_member"


def _pdf_bytes() -> bytes:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(200, 200)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()
