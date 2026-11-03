"""Gemini prompt and response schema for bill extraction."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.rules.bill_types import BILL_TYPES


class ExtractedBill(BaseModel):
    bill_type: str | None = Field(
        default=None,
        description="One slug from the fixed list, or null when none fits.",
    )
    merchant: str | None = Field(default=None, description="Seller or utility name.")
    amount: float | None = Field(
        default=None, description="Final payable total; never a line item or amount due."
    )
    currency: str | None = Field(default=None, description="ISO-4217 code, usually INR.")
    bill_date: str | None = Field(
        default=None, description="Bill/invoice date in YYYY-MM-DD form, not a due date."
    )
    language: Literal["en", "hi", "mr", "mixed", "other"] | None = None
    raw_text: str | None = Field(default=None, description="Readable text in the bill's script.")
    tags: list[str] = Field(
        default_factory=list,
        description="At most three short descriptive tags, not repeating bill_type.",
    )


def system_prompt() -> str:
    listing = "\n".join(f"- {slug}: {label}" for slug, label in BILL_TYPES)
    return f"""You extract structured data from household bills and receipts.

Return only the JSON object described by the schema.

Rules:
- bill_type must be exactly one of these slugs, or null:
{listing}
- Return null for any field you cannot read with confidence. Never guess an amount or date.
- amount is the final payable total (prefer "Grand Total" / "Net Payable"), not a line
  item and not an outstanding or due amount.
- bill_date is the bill/invoice date, never the due date.
- merchant is the seller or utility, never the customer.
- raw_text should be the readable bill text in the bill's own script.
- Give at most three short descriptive tags (English) and do not repeat bill_type.
- language is one of en, hi, mr, mixed, other.
"""


def user_prompt(page_count: int) -> str:
    noun = "page" if page_count == 1 else "pages"
    return f"Extract the bill fields from the attached {page_count} {noun}."
