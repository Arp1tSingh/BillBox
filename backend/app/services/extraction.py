"""Bill extraction providers: live Gemini and a deterministic mock."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Protocol

from app.config import Settings
from app.domain import ExtractionResult
from app.prompts.extract import ExtractedBill, system_prompt, user_prompt

logger = logging.getLogger(__name__)


class ExtractionError(Exception):
    """A user-safe extraction failure."""

    def __init__(
        self, message: str = "Could not read this bill.", *, retryable: bool = True
    ) -> None:
        super().__init__(message)
        self.user_message = message
        self.retryable = retryable


class ExtractionProvider(Protocol):
    async def extract(self, pages: list[tuple[bytes, str]]) -> ExtractionResult: ...


def _to_result(payload: ExtractedBill) -> ExtractionResult:
    from app.rules.bill_types import BILL_TYPE_SLUGS

    bill_type = payload.bill_type if payload.bill_type in BILL_TYPE_SLUGS else None
    amount: Decimal | None = None
    if payload.amount is not None:
        try:
            amount = Decimal(str(payload.amount)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            amount = None
    bill_date: date | None = None
    if payload.bill_date:
        try:
            bill_date = date.fromisoformat(payload.bill_date[:10])
        except ValueError:
            bill_date = None
    currency = (payload.currency or "INR").upper()[:3]
    tags = [tag.strip() for tag in payload.tags if tag and tag.strip()][:3]
    return ExtractionResult(
        bill_type=bill_type,
        merchant=payload.merchant.strip() if payload.merchant else None,
        amount=amount,
        currency=currency,
        bill_date=bill_date,
        language=payload.language,
        raw_text=payload.raw_text,
        tags=tags,
    )


class MockExtractionProvider(ExtractionProvider):
    """Deterministic output so automated tests never call Gemini."""

    async def extract(self, pages: list[tuple[bytes, str]]) -> ExtractionResult:
        await asyncio.sleep(0)
        if not pages:
            raise ExtractionError("No pages to read.", retryable=False)
        return ExtractionResult(
            bill_type="groceries",
            merchant="Demo Store",
            amount=Decimal("1234.50"),
            currency="INR",
            bill_date=date(2026, 1, 15),
            language="en",
            raw_text="Demo Store grocery bill total 1234.50",
            tags=["demo", "grocery"],
        )


class FailingExtractionProvider(ExtractionProvider):
    """Used by tests and the failure-path E2E."""

    def __init__(self, message: str = "AI quota reached") -> None:
        self.message = message

    async def extract(self, pages: list[tuple[bytes, str]]) -> ExtractionResult:
        raise ExtractionError(self.message)


def _retryable(exc: Exception) -> bool:
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if isinstance(code, int):
        return code == 429 or code >= 500
    text = str(exc)
    return any(marker in text for marker in ("429", "500", "502", "503", "504"))


class GeminiExtractionProvider(ExtractionProvider):
    def __init__(self, settings: Settings) -> None:
        if not settings.gemini_api_key:
            raise ExtractionError("AI extraction is not configured.", retryable=False)
        from google import genai

        self._genai = genai
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model
        self._thinking_level = settings.gemini_thinking_level

    async def extract(self, pages: list[tuple[bytes, str]]) -> ExtractionResult:
        if not pages:
            raise ExtractionError("No pages to read.", retryable=False)

        from google.genai import types

        parts = [
            types.Part.from_bytes(data=data, mime_type=mime_type)
            for data, mime_type in pages
        ]
        config = types.GenerateContentConfig(
            system_instruction=system_prompt(),
            response_mime_type="application/json",
            response_schema=ExtractedBill,
            max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_level=self._thinking_level),
        )
        contents = [*parts, user_prompt(len(pages))]

        last_error: Exception | None = None
        for attempt in range(4):
            try:
                response = await self._client.aio.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                return self._parse(response)
            except ExtractionError:
                raise
            except Exception as exc:  # noqa: BLE001 - provider-specific errors vary
                last_error = exc
                if not _retryable(exc) or attempt == 3:
                    break
                delay = 2 * (2**attempt)
                logger.info(
                    "gemini_retry",
                    extra={"attempt": attempt + 1, "delay_s": delay, "reason": type(exc).__name__},
                )
                await asyncio.sleep(delay)

        logger.warning("gemini_extraction_failed", extra={"reason": type(last_error).__name__})
        raise ExtractionError("Could not read this bill right now. Try again.")

    def _parse(self, response: object) -> ExtractionResult:
        parsed = getattr(response, "parsed", None)
        if isinstance(parsed, ExtractedBill):
            return _to_result(parsed)
        if isinstance(parsed, dict):
            return _to_result(ExtractedBill.model_validate(parsed))
        text = getattr(response, "text", None)
        if not text:
            raise ExtractionError("The AI response was empty. Try again.")
        try:
            payload = ExtractedBill.model_validate(json.loads(text))
        except (json.JSONDecodeError, ValueError) as exc:
            logger.info("gemini_parse_failed", extra={"reason": type(exc).__name__})
            raise ExtractionError("Could not understand the AI response. Try again.") from exc
        return _to_result(payload)


@dataclass(frozen=True)
class ExtractionProviderFactory:
    settings: Settings

    def build(self) -> ExtractionProvider:
        if self.settings.gemini_mock:
            return MockExtractionProvider()
        try:
            return GeminiExtractionProvider(self.settings)
        except ExtractionError:
            return FailingExtractionProvider("AI extraction is not configured.")


def build_extraction_provider(settings: Settings) -> ExtractionProvider:
    return ExtractionProviderFactory(settings).build()
