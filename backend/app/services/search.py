"""Natural-language query parsing and ranked receipt search."""

from __future__ import annotations

import re
import unicodedata
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from app.domain import AuthUser, Tag
from app.repositories.base import ReceiptsRepository
from app.schemas.receipts import ReceiptSearchResponse, ReceiptSummaryView
from app.services.households import HouseholdService
from app.services.storage import StorageService

KOLKATA = ZoneInfo("Asia/Kolkata")
Sort = Literal["date", "amount", "relevance"]

_MONTHS = {
    "jan": 1, "january": 1,
    "feb": 2, "february": 2,
    "mar": 3, "march": 3,
    "apr": 4, "april": 4,
    "may": 5,
    "jun": 6, "june": 6,
    "jul": 7, "july": 7,
    "aug": 8, "august": 8,
    "sep": 9, "sept": 9, "september": 9,
    "oct": 10, "october": 10,
    "nov": 11, "november": 11,
    "dec": 12, "december": 12,
}
_MONTH_ALT = "|".join(sorted(_MONTHS, key=len, reverse=True))

_AMOUNT = r"(?:rs\.?|inr|\u20b9)?\s*([\d,]+(?:\.\d+)?)"
_BETWEEN_RE = re.compile(rf"\bbetween\s+{_AMOUNT}\s+(?:and|to)\s+{_AMOUNT}", re.I)
_OVER_RE = re.compile(rf"(?:>|\bover\b|\babove\b|\bmore than\b|\bgreater than\b)\s*{_AMOUNT}", re.I)
_UNDER_RE = re.compile(
    rf"(?:<|\bunder\b|\bbelow\b|\bless than\b|\bcheaper than\b)\s*{_AMOUNT}", re.I
)
_MONTH_YEAR_RE = re.compile(rf"\b({_MONTH_ALT})\s+(\d{{4}})\b", re.I)
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_WHITESPACE = re.compile(r"\s+")


def _amount(value: str) -> Decimal | None:
    try:
        return Decimal(value.replace(",", "")).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError):
        return None


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    return date(year, month, 1), date(year, month, monthrange(year, month)[1])


def _previous_month(day: date) -> tuple[int, int]:
    return (day.year - 1, 12) if day.month == 1 else (day.year, day.month - 1)


@dataclass
class ParsedQuery:
    text: str | None = None
    tag_ids: list[UUID] = field(default_factory=list)
    date_from: date | None = None
    date_to: date | None = None
    min_amount: Decimal | None = None
    max_amount: Decimal | None = None


class SearchParser:
    def __init__(self, tags: list[Tag], *, today: date | None = None) -> None:
        self.tags = tags
        self.today = today or datetime.now(KOLKATA).date()

    def parse(self, raw: str | None) -> ParsedQuery:
        working = unicodedata.normalize("NFC", raw or "")
        parsed = ParsedQuery()

        working = self._parse_amounts(working, parsed)
        working = self._parse_dates(working, parsed)
        working = self._parse_tags(working, parsed)

        cleaned = _WHITESPACE.sub(" ", working).strip(" .,-")
        parsed.text = cleaned or None
        return parsed

    def _parse_amounts(self, text: str, parsed: ParsedQuery) -> str:
        def between(match: re.Match[str]) -> str:
            low = _amount(match.group(1))
            high = _amount(match.group(2))
            if low is not None and high is not None:
                parsed.min_amount, parsed.max_amount = min(low, high), max(low, high)
            return " "

        def over(match: re.Match[str]) -> str:
            value = _amount(match.group(1))
            if value is not None:
                parsed.min_amount = value
            return " "

        def under(match: re.Match[str]) -> str:
            value = _amount(match.group(1))
            if value is not None:
                parsed.max_amount = value
            return " "

        text = _BETWEEN_RE.sub(between, text)
        text = _OVER_RE.sub(over, text)
        return _UNDER_RE.sub(under, text)

    def _parse_dates(self, text: str, parsed: ParsedQuery) -> str:
        lowered = text.casefold()

        def set_range(start: date, end: date) -> None:
            parsed.date_from, parsed.date_to = start, end

        if "last month" in lowered:
            year, month = _previous_month(self.today)
            set_range(*_month_bounds(year, month))
            text = re.sub(r"\blast\s+month\b", " ", text, flags=re.I)
        elif "this month" in lowered:
            set_range(*_month_bounds(self.today.year, self.today.month))
            text = re.sub(r"\bthis\s+month\b", " ", text, flags=re.I)
        elif "last year" in lowered:
            set_range(date(self.today.year - 1, 1, 1), date(self.today.year - 1, 12, 31))
            text = re.sub(r"\blast\s+year\b", " ", text, flags=re.I)
        elif "this year" in lowered:
            set_range(date(self.today.year, 1, 1), date(self.today.year, 12, 31))
            text = re.sub(r"\bthis\s+year\b", " ", text, flags=re.I)

        if parsed.date_from is None:
            month_match = _MONTH_YEAR_RE.search(text)
            if month_match:
                month = _MONTHS[month_match.group(1).casefold()]
                year = int(month_match.group(2))
                set_range(*_month_bounds(year, month))
                text = text[: month_match.start()] + " " + text[month_match.end() :]

        if parsed.date_from is None:
            year_match = _YEAR_RE.search(text)
            if year_match:
                year = int(year_match.group(1))
                set_range(date(year, 1, 1), date(year, 12, 31))
                text = text[: year_match.start()] + " " + text[year_match.end() :]

        return text

    def _parse_tags(self, text: str, parsed: ParsedQuery) -> str:
        candidates: list[tuple[str, Tag]] = []
        for tag in self.tags:
            phrases = [tag.label_en, tag.label_hi, tag.label_mr, *tag.keywords]
            seen: set[str] = set()
            for phrase in phrases:
                if not phrase:
                    continue
                normal = unicodedata.normalize("NFC", phrase).strip()
                key = normal.casefold()
                if len(normal) < 3 or key in seen:
                    continue
                seen.add(key)
                candidates.append((normal, tag))
        candidates.sort(key=lambda item: len(item[0]), reverse=True)

        for phrase, tag in candidates:
            pattern = re.compile(rf"(?<!\w){re.escape(phrase)}(?!\w)", re.I)
            if pattern.search(text):
                if tag.id not in parsed.tag_ids:
                    parsed.tag_ids.append(tag.id)
                text = pattern.sub(" ", text)
        return text


def resolve_tag_filters(values: list[str], tags: list[Tag]) -> list[UUID]:
    resolved: list[UUID] = []
    for value in values:
        needle = value.strip().casefold()
        if not needle:
            continue
        for tag in tags:
            labels = {
                tag.slug.casefold(),
                (tag.label_en or "").casefold(),
                (tag.label_hi or "").casefold(),
                (tag.label_mr or "").casefold(),
                str(tag.id),
            }
            if needle in labels and tag.id not in resolved:
                resolved.append(tag.id)
                break
    return resolved


class SearchService:
    def __init__(
        self,
        repo: ReceiptsRepository,
        households: HouseholdService,
        storage: StorageService,
    ) -> None:
        self.repo = repo
        self.households = households
        self.storage = storage

    async def search(
        self,
        user: AuthUser,
        *,
        q: str | None = None,
        tag: list[str] | None = None,
        date_from: date | None = None,
        date_to: date | None = None,
        min_amount: Decimal | None = None,
        max_amount: Decimal | None = None,
        sort: str = "date",
        page: int = 1,
        page_size: int = 20,
        household_header: UUID | None = None,
    ) -> ReceiptSearchResponse:
        membership = await self.households.require_membership(user, household_header)
        tags = await self.repo.list_tags(membership.household_id)
        parsed = SearchParser(tags).parse(q)

        if tag:
            tag_ids = resolve_tag_filters(tag, tags)
            # A query such as "electricity" also resolves to a tag. Keep that
            # filter alongside the chip selection so text + chip remains an
            # AND filter (for example, electricity text + Groceries chip).
            for parsed_tag_id in parsed.tag_ids:
                if parsed_tag_id not in tag_ids:
                    tag_ids.append(parsed_tag_id)
        else:
            tag_ids = parsed.tag_ids
        start = date_from or parsed.date_from
        end = date_to or parsed.date_to
        low = min_amount if min_amount is not None else parsed.min_amount
        high = max_amount if max_amount is not None else parsed.max_amount
        order: Sort = sort if sort in ("date", "amount", "relevance") else "date"
        safe_page = max(1, page)
        safe_size = max(1, min(page_size, 50))

        receipts, total = await self.repo.search_receipts(
            membership.household_id,
            query=parsed.text,
            tag_ids=tag_ids,
            date_from=start,
            date_to=end,
            min_amount=low,
            max_amount=high,
            sort=order,
            limit=safe_size,
            offset=(safe_page - 1) * safe_size,
        )

        items: list[ReceiptSummaryView] = []
        for receipt in receipts:
            pages = await self.repo.list_pages(receipt.id)
            thumbnail = await self.storage.signed_url(pages[0].storage_path) if pages else None
            items.append(
                ReceiptSummaryView(
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
                    thumbnail_url=thumbnail,
                )
            )
        return ReceiptSearchResponse(
            items=items, total=total, page=safe_page, page_size=safe_size
        )
