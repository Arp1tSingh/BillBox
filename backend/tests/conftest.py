"""Shared fixtures for fast, database-free backend tests."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.domain import AuthUser, ExtractionResult
from app.errors import AuthError
from app.main import create_app
from tests.fakes import (
    FakeHouseholdsRepository,
    FakeReceiptsRepository,
    FakeStorage,
    ScriptedExtractionProvider,
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if os.getenv("RUN_E2E") == "1":
        return
    skip = pytest.mark.skip(reason="Set RUN_E2E=1 and a local Supabase env to run E2E tests.")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)



class StaticTokenVerifier:
    def __init__(self, users: dict[str, AuthUser]) -> None:
        self.users = users

    async def verify(self, token: str) -> AuthUser:
        user = self.users.get(token)
        if user is None:
            raise AuthError()
        return user


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="test",
        supabase_url="http://supabase.test",
        supabase_anon_key="test-anon",
        supabase_service_role_key="test-service",
        supabase_jwt_secret="test-jwt-secret-that-is-long-enough",
        cors_origins="http://localhost:5173",
    )


@pytest.fixture
def repo(settings: Settings) -> FakeHouseholdsRepository:
    return FakeHouseholdsRepository(max_members=settings.max_household_members)


@pytest.fixture
def users(repo: FakeHouseholdsRepository) -> dict[str, AuthUser]:
    result = {
        "owner": AuthUser(uuid4(), "owner@example.com", "authenticated"),
        "member": AuthUser(uuid4(), "member@example.com", "authenticated"),
        "outsider": AuthUser(uuid4(), "outsider@example.com", "authenticated"),
    }
    for user in result.values():
        assert user.email is not None
        repo.set_email(user.id, user.email)
    return result


@pytest.fixture
def receipts_repo() -> FakeReceiptsRepository:
    return FakeReceiptsRepository()


@pytest.fixture
def storage() -> FakeStorage:
    return FakeStorage()


@pytest.fixture
def extraction() -> ScriptedExtractionProvider:
    return ScriptedExtractionProvider(
        result=ExtractionResult(
            bill_type="electricity",
            merchant="Adani Electricity Pvt Ltd",
            amount=Decimal("2480.50"),
            currency="INR",
            bill_date=date(2026, 1, 12),
            language="en",
            raw_text="Adani Electricity bill total 2480.50",
            tags=["power", "monthly"],
        )
    )


@pytest_asyncio.fixture
async def client(
    settings: Settings,
    repo: FakeHouseholdsRepository,
    receipts_repo: FakeReceiptsRepository,
    storage: FakeStorage,
    extraction: ScriptedExtractionProvider,
    users: dict[str, AuthUser],
) -> AsyncIterator[AsyncClient]:
    app = create_app(
        settings=settings,
        households_repo=repo,
        receipts_repo=receipts_repo,
        storage=storage,
        extraction=extraction,
        jwt_verifier=StaticTokenVerifier(users),
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
