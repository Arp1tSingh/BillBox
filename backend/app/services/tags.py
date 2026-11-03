"""Tag listing for the household."""

from __future__ import annotations

from app.domain import AuthUser
from app.repositories.base import ReceiptsRepository
from app.schemas.tags import TagView
from app.services.households import HouseholdService


class TagService:
    def __init__(self, repo: ReceiptsRepository, households: HouseholdService) -> None:
        self.repo = repo
        self.households = households

    async def list_for_user(self, user: AuthUser, household_header=None) -> list[TagView]:
        membership = await self.households.require_membership(user, household_header)
        tags = await self.repo.list_tags(membership.household_id)
        counts = await self.repo.tag_counts(membership.household_id)
        views = [
            TagView(
                id=tag.id,
                slug=tag.slug,
                label_en=tag.label_en,
                label_hi=tag.label_hi,
                label_mr=tag.label_mr,
                kind=tag.kind,
                keywords=tag.keywords,
                count=counts.get(tag.id, 0),
            )
            for tag in tags
        ]
        views.sort(key=lambda tag: (-tag.count, tag.kind, tag.label_en.casefold()))
        return views
