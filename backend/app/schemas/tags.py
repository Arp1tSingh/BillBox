"""Tag responses."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel


class TagView(BaseModel):
    id: UUID
    slug: str
    label_en: str
    label_hi: str | None = None
    label_mr: str | None = None
    kind: str
    keywords: list[str]
    count: int = 0
