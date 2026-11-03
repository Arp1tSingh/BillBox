"""Household export as a ZIP of CSV metadata and original page files."""

from __future__ import annotations

import csv
import io
import logging
import tempfile
import zipfile
from collections.abc import Iterator
from datetime import UTC, datetime
from uuid import UUID

from app.domain import AuthUser, Receipt
from app.repositories.base import ReceiptsRepository
from app.services.households import HouseholdService
from app.services.storage import StorageService

logger = logging.getLogger(__name__)

EXPORT_LIMIT = 500
_EXTENSIONS = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}


class ExportService:
    def __init__(
        self,
        repo: ReceiptsRepository,
        households: HouseholdService,
        storage: StorageService,
    ) -> None:
        self.repo = repo
        self.households = households
        self.storage = storage

    async def export(
        self, user: AuthUser, *, household_header: UUID | None = None
    ) -> tuple[Iterator[bytes], str]:
        membership = await self.households.require_membership(user, household_header)
        receipts = await self.repo.list_receipts(membership.household_id, limit=EXPORT_LIMIT)

        csv_buffer = io.StringIO(newline="")
        writer = csv.writer(csv_buffer)
        writer.writerow(
            [
                "Receipt ID",
                "Title",
                "Merchant",
                "Amount",
                "Currency",
                "Bill date",
                "Bill type",
                "Status",
                "AI skipped",
                "Failure reason",
                "Language",
                "Tags",
                "Pages",
                "Created at",
            ]
        )

        export_file = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)  # noqa: SIM115
        try:
            with zipfile.ZipFile(export_file, "w", zipfile.ZIP_DEFLATED) as archive:
                for receipt in receipts:
                    tags = await self.repo.list_receipt_tags(receipt.id)
                    active = [row.tag.label_en for row in tags if row.removed_at is None]
                    pages = await self.repo.list_pages(receipt.id)
                    writer.writerow(self._row(receipt, active, len(pages)))
                    for page in pages:
                        extension = _EXTENSIONS.get(page.mime_type, "bin")
                        name = f"pages/{receipt.id}/{page.page_no}.{extension}"
                        try:
                            data = await self.storage.download(page.storage_path)
                        except Exception:
                            logger.warning(
                                "export_page_missing",
                                extra={"receipt_id": str(receipt.id), "page_no": page.page_no},
                            )
                            continue
                        archive.writestr(name, data)

                archive.writestr("receipts.csv", csv_buffer.getvalue().encode("utf-8-sig"))
            export_file.seek(0)
        except Exception:
            export_file.close()
            raise

        def chunks() -> Iterator[bytes]:
            try:
                while chunk := export_file.read(64 * 1024):
                    yield chunk
            finally:
                export_file.close()

        stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        return chunks(), f"billbox-export-{stamp}.zip"

    @staticmethod
    def _row(receipt: Receipt, tags: list[str], page_count: int) -> list[object]:
        return [
            str(receipt.id),
            receipt.title or "",
            receipt.merchant or "",
            str(receipt.amount) if receipt.amount is not None else "",
            receipt.currency,
            receipt.bill_date.isoformat() if receipt.bill_date else "",
            receipt.bill_type or "",
            receipt.status,
            "yes" if receipt.ai_skipped else "no",
            receipt.failure_reason or "",
            receipt.language or "",
            "; ".join(tags),
            page_count,
            receipt.created_at.isoformat(),
        ]
