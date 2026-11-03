"""Receipt capture, processing, detail and manual edit rules."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from uuid import UUID

from fastapi import UploadFile

from app.config import Settings
from app.domain import AuthUser, ExtractionResult, Receipt
from app.errors import AppError, NotFoundError
from app.repositories.base import ReceiptsRepository
from app.rules.bill_types import BILL_TYPE_LABELS
from app.schemas.receipts import (
    ReceiptDetailView,
    ReceiptPageView,
    ReceiptSummaryView,
    ReceiptTagView,
    ReceiptUploadView,
)
from app.services.extraction import ExtractionError, ExtractionProvider
from app.services.households import HouseholdService
from app.services.storage import StorageService, build_storage_path
from app.services.tagging import TaggingService

logger = logging.getLogger(__name__)

_ALLOWED_TYPES = {
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "application/pdf": "pdf",
}
_CHUNK = 1024 * 1024


class ReceiptService:
    def __init__(
        self,
        repo: ReceiptsRepository,
        households: HouseholdService,
        storage: StorageService,
        extraction: ExtractionProvider,
        settings: Settings,
    ) -> None:
        self.repo = repo
        self.households = households
        self.storage = storage
        self.extraction = extraction
        self.settings = settings
        self.tagging = TaggingService(repo)

    async def upload(
        self,
        user: AuthUser,
        files: Sequence[UploadFile],
        *,
        skip_ai: bool = False,
        household_header: UUID | None = None,
    ) -> ReceiptUploadView:
        membership = await self.households.require_membership(user, household_header)
        validated = await self._validate(files)

        now = datetime.now(UTC)
        receipt = await self.repo.create_receipt(
            household_id=membership.household_id,
            created_by=user.id,
            status="ready" if skip_ai else "processing",
            ai_skipped=skip_ai,
            extracted={"skipped": True} if skip_ai else None,
            processed_at=now.isoformat() if skip_ai else None,
        )

        stored_paths: list[str] = []
        try:
            for page_no, (data, mime_type, ext) in enumerate(validated, start=1):
                path = build_storage_path(
                    membership.household_id, receipt.id, page_no, ext
                )
                await self.storage.upload(path, data, mime_type)
                stored_paths.append(path)
                await self.repo.add_page(
                    receipt_id=receipt.id,
                    page_no=page_no,
                    storage_path=path,
                    mime_type=mime_type,
                    size_bytes=len(data),
                )
        except Exception as exc:
            logger.warning(
                "upload_rollback",
                extra={"receipt_id": str(receipt.id), "reason": type(exc).__name__},
            )
            await self._safe_delete(stored_paths)
            await self.repo.delete_receipt(receipt.id, membership.household_id)
            if isinstance(exc, AppError):
                raise
            raise AppError(502, "upload_failed", "Could not save the pages. Try again.") from exc

        logger.info(
            "receipt_uploaded",
            extra={
                "receipt_id": str(receipt.id),
                "household_id": str(membership.household_id),
                "pages": len(validated),
                "skip_ai": skip_ai,
            },
        )
        return ReceiptUploadView(id=receipt.id, status="ready" if skip_ai else "processing")

    async def process(
        self, user: AuthUser, receipt_id: UUID, *, household_header: UUID | None = None
    ) -> ReceiptDetailView:
        membership = await self.households.require_membership(user, household_header)
        receipt = await self.repo.get_receipt(receipt_id, membership.household_id)
        if receipt is None:
            raise NotFoundError("Receipt not found.", "receipt_not_found")

        claimed = await self.repo.claim_receipt(
            receipt_id,
            membership.household_id,
            stale_after_seconds=self.settings.processing_stale_seconds,
        )
        if claimed is None:
            return await self.detail(user, receipt_id, household_header=household_header)

        if claimed.ai_skipped:
            await self.repo.update_receipt(
                receipt_id,
                membership.household_id,
                {"status": "ready", "processing_started_at": None},
            )
            return await self.detail(user, receipt_id, household_header=household_header)

        pages = await self.repo.list_pages(receipt_id)
        try:
            payloads: list[tuple[bytes, str]] = []
            for page in pages:
                payloads.append((await self.storage.download(page.storage_path), page.mime_type))
            if not payloads:
                raise ExtractionError("No pages to read.", retryable=False)
            result = await self.extraction.extract(payloads)
            fields = self._extraction_fields(claimed, result)
            await self.repo.update_receipt(receipt_id, membership.household_id, fields)
            bill_type = await self.tagging.apply(
                await self.repo.get_receipt(receipt_id, membership.household_id) or claimed,
                result,
            )
            if bill_type != fields.get("bill_type"):
                await self.repo.update_receipt(
                    receipt_id, membership.household_id, {"bill_type": bill_type}
                )
            logger.info(
                "receipt_processed",
                extra={"receipt_id": str(receipt_id), "household_id": str(membership.household_id)},
            )
        except ExtractionError as exc:
            logger.info(
                "receipt_process_failed",
                extra={"receipt_id": str(receipt_id), "reason": type(exc).__name__},
            )
            await self.repo.update_receipt(
                receipt_id,
                membership.household_id,
                {
                    "status": "failed",
                    "failure_reason": exc.user_message,
                    "processing_started_at": None,
                    "processed_at": datetime.now(UTC).isoformat(),
                },
            )
        except Exception as exc:  # noqa: BLE001 - keep the row retryable
            logger.warning(
                "receipt_process_error",
                extra={"receipt_id": str(receipt_id), "reason": type(exc).__name__},
            )
            await self.repo.update_receipt(
                receipt_id,
                membership.household_id,
                {
                    "status": "failed",
                    "failure_reason": "Could not read this bill right now. Try again.",
                    "processing_started_at": None,
                    "processed_at": datetime.now(UTC).isoformat(),
                },
            )

        return await self.detail(user, receipt_id, household_header=household_header)

    async def detail(
        self, user: AuthUser, receipt_id: UUID, *, household_header: UUID | None = None
    ) -> ReceiptDetailView:
        membership = await self.households.require_membership(user, household_header)
        receipt = await self.repo.get_receipt(receipt_id, membership.household_id)
        if receipt is None:
            raise NotFoundError("Receipt not found.", "receipt_not_found")
        pages = await self.repo.list_pages(receipt_id)
        page_views = [
            ReceiptPageView(
                page_no=page.page_no,
                mime_type=page.mime_type,
                size_bytes=page.size_bytes,
                url=await self.storage.signed_url(page.storage_path),
            )
            for page in pages
        ]
        tags = [
            ReceiptTagView(
                tag_id=row.tag.id,
                slug=row.tag.slug,
                label_en=row.tag.label_en,
                label_hi=row.tag.label_hi,
                label_mr=row.tag.label_mr,
                kind=row.tag.kind,
                source=row.source,
                confidence=row.confidence,
            )
            for row in await self.repo.list_receipt_tags(receipt_id)
            if row.removed_at is None
        ]
        return ReceiptDetailView(
            **self._summary(receipt).model_dump(),
            language=receipt.language,
            raw_text=receipt.raw_text,
            extracted=receipt.extracted,
            pages=page_views,
            tags=tags,
            processed_at=receipt.processed_at,
        )

    async def list(
        self,
        user: AuthUser,
        *,
        limit: int = 20,
        household_header: UUID | None = None,
    ) -> list[ReceiptSummaryView]:
        membership = await self.households.require_membership(user, household_header)
        receipts = await self.repo.list_receipts(membership.household_id, limit=limit)
        result: list[ReceiptSummaryView] = []
        for receipt in receipts:
            summary = self._summary(receipt)
            pages = await self.repo.list_pages(receipt.id)
            if pages:
                summary.thumbnail_url = await self.storage.signed_url(pages[0].storage_path)
            result.append(summary)
        return result

    async def update(
        self,
        user: AuthUser,
        receipt_id: UUID,
        fields: dict[str, object],
        *,
        household_header: UUID | None = None,
    ) -> ReceiptDetailView:
        membership = await self.households.require_membership(user, household_header)
        if await self.repo.get_receipt(receipt_id, membership.household_id) is None:
            raise NotFoundError("Receipt not found.", "receipt_not_found")
        clean: dict[str, object] = {}
        for key, value in fields.items():
            if isinstance(value, (date, Decimal)):
                clean[key] = value.isoformat() if isinstance(value, date) else str(value)
            else:
                clean[key] = value
        if clean:
            await self.repo.update_receipt(receipt_id, membership.household_id, clean)
        return await self.detail(user, receipt_id, household_header=household_header)

    async def delete(
        self, user: AuthUser, receipt_id: UUID, *, household_header: UUID | None = None
    ) -> None:
        membership = await self.households.require_membership(user, household_header)
        receipt = await self.repo.get_receipt(receipt_id, membership.household_id)
        if receipt is None:
            raise NotFoundError("Receipt not found.", "receipt_not_found")
        pages = await self.repo.list_pages(receipt_id)
        await self._safe_delete([page.storage_path for page in pages])
        await self.repo.delete_receipt(receipt_id, membership.household_id)

    async def add_tag(
        self,
        user: AuthUser,
        receipt_id: UUID,
        *,
        tag_id: UUID | None = None,
        label: str | None = None,
        household_header: UUID | None = None,
    ) -> ReceiptDetailView:
        membership = await self.households.require_membership(user, household_header)
        receipt = await self.repo.get_receipt(receipt_id, membership.household_id)
        if receipt is None:
            raise NotFoundError("Receipt not found.", "receipt_not_found")
        try:
            await self.tagging.add_user_tag(receipt, user.id, tag_id=tag_id, label=label)
        except LookupError as exc:
            raise NotFoundError("That tag does not exist.", "tag_not_found") from exc
        except ValueError as exc:
            raise AppError(422, "tag_label_required", "Give the tag a name.") from exc
        return await self.detail(user, receipt_id, household_header=household_header)

    async def remove_tag(
        self,
        user: AuthUser,
        receipt_id: UUID,
        tag_id: UUID,
        *,
        household_header: UUID | None = None,
    ) -> ReceiptDetailView:
        membership = await self.households.require_membership(user, household_header)
        receipt = await self.repo.get_receipt(receipt_id, membership.household_id)
        if receipt is None:
            raise NotFoundError("Receipt not found.", "receipt_not_found")
        await self.repo.remove_receipt_tag(receipt_id=receipt_id, tag_id=tag_id, user_id=user.id)
        remaining = [
            row.tag
            for row in await self.repo.list_receipt_tags(receipt_id)
            if row.removed_at is None
        ]
        bill_type = next((tag.slug for tag in remaining if tag.kind == "bill_type"), None)
        await self.repo.update_receipt(
            receipt_id, membership.household_id, {"bill_type": bill_type}
        )
        return await self.detail(user, receipt_id, household_header=household_header)

    async def _validate(
        self, files: Sequence[UploadFile]
    ) -> list[tuple[bytes, str, str]]:
        import filetype

        if not files:
            raise AppError(422, "no_files", "Add at least one page.")
        if len(files) > self.settings.max_pages:
            raise AppError(
                422,
                "too_many_pages",
                f"Bills can have at most {self.settings.max_pages} pages.",
            )

        max_file = self.settings.max_file_mb * 1024 * 1024
        max_total = self.settings.max_upload_mb * 1024 * 1024
        total = 0
        validated: list[tuple[bytes, str, str]] = []

        for upload in files:
            data = bytearray()
            while chunk := await upload.read(_CHUNK):
                total += len(chunk)
                if len(data) + len(chunk) > max_file:
                    raise AppError(
                        413,
                        "file_too_large",
                        f"Each page must be under {self.settings.max_file_mb} MB.",
                    )
                if total > max_total:
                    raise AppError(
                        413,
                        "upload_too_large",
                        f"Keep the whole bill under {self.settings.max_upload_mb} MB.",
                    )
                data.extend(chunk)
            if not data:
                raise AppError(422, "empty_file", "One of the pages is empty.")

            kind = filetype.guess(bytes(data))
            mime_type = kind.mime if kind else (upload.content_type or "")
            ext = _ALLOWED_TYPES.get(mime_type)
            if ext is None:
                raise AppError(
                    422,
                    "unsupported_file_type",
                    "Use JPEG, PNG, WebP images or a PDF.",
                )
            validated.append((bytes(data), mime_type, ext))

        pdfs = [item for item in validated if item[1] == "application/pdf"]
        if pdfs and len(validated) > 1:
            raise AppError(422, "pdf_mixed_with_images", "Upload one PDF or up to 10 images.")
        if pdfs:
            self._validate_pdf(pdfs[0][0])
        return validated

    def _validate_pdf(self, data: bytes) -> None:
        from pypdf import PdfReader

        try:
            reader = PdfReader(BytesIO(data))
            if reader.is_encrypted:
                raise AppError(422, "encrypted_pdf", "Remove the PDF password and try again.")
            page_count = len(reader.pages)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(422, "invalid_pdf", "That PDF could not be read.") from exc
        if page_count < 1:
            raise AppError(422, "empty_pdf", "That PDF has no pages.")
        if page_count > self.settings.max_pages:
            raise AppError(
                422,
                "too_many_pdf_pages",
                f"PDFs can have at most {self.settings.max_pages} pages.",
            )

    def _extraction_fields(self, receipt: Receipt, result: ExtractionResult) -> dict[str, object]:
        title = receipt.title or self._default_title(result)
        return {
            "status": "ready",
            "failure_reason": None,
            "processing_started_at": None,
            "processed_at": datetime.now(UTC).isoformat(),
            "merchant": result.merchant,
            "amount": str(result.amount) if result.amount is not None else None,
            "currency": result.currency or "INR",
            "bill_date": result.bill_date.isoformat() if result.bill_date else None,
            "bill_type": result.bill_type,
            "language": result.language,
            "raw_text": result.raw_text,
            "extracted": {
                "bill_type": result.bill_type,
                "merchant": result.merchant,
                "amount": str(result.amount) if result.amount is not None else None,
                "currency": result.currency,
                "bill_date": result.bill_date.isoformat() if result.bill_date else None,
                "language": result.language,
                "tags": result.tags,
            },
            "title": title,
        }

    def _default_title(self, result: ExtractionResult) -> str:
        label = result.merchant or BILL_TYPE_LABELS.get(result.bill_type or "", "Bill")
        when = result.bill_date or datetime.now(UTC).date()
        return f"{label} \u2014 {when:%b %Y}"

    def _summary(self, receipt: Receipt) -> ReceiptSummaryView:
        return ReceiptSummaryView(
            id=receipt.id,
            title=receipt.title,
            merchant=receipt.merchant,
            amount=receipt.amount,
            currency=receipt.currency,
            bill_date=receipt.bill_date,
            bill_type=receipt.bill_type,
            status=receipt.status,
            ai_skipped=receipt.ai_skipped,
            failure_reason=receipt.failure_reason,
            created_at=receipt.created_at,
        )

    async def _safe_delete(self, paths: list[str]) -> None:
        try:
            await self.storage.delete(paths)
        except Exception as exc:  # noqa: BLE001 - deletion is best effort
            logger.warning("storage_delete_failed", extra={"reason": type(exc).__name__})
