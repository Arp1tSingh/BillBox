"""Fixtures for API-level E2E tests against a real local Supabase."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.main import create_app


def _load_e2e_env() -> None:
    """Load the root .env.e2e so `pytest -m e2e` works without shell exports."""
    root = Path(__file__).resolve().parents[3]
    for name, override in ((".env.e2e", False), (".env.e2e.local", True)):
        path = root / name
        if not path.is_file():
            continue
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and (override or key not in os.environ):
                os.environ[key] = value


_load_e2e_env()

PASSWORD = "BillBox-e2e-123!"
UserFactory = Callable[[str], Awaitable["LiveUser"]]


@dataclass(frozen=True)
class LiveUser:
    id: str
    email: str
    token: str


def _require_env(name: str) -> str:
    value = os.getenv(name, "")
    if not value:
        pytest.skip(f"{name} is not set; start local Supabase and source .env.e2e")
    return value


@pytest.fixture(scope="session")
def live_settings() -> Settings:
    return Settings(
        environment="test",
        supabase_url=_require_env("SUPABASE_URL"),
        supabase_anon_key=_require_env("SUPABASE_ANON_KEY"),
        supabase_service_role_key=_require_env("SUPABASE_SERVICE_ROLE_KEY"),
        supabase_jwt_secret=os.getenv("SUPABASE_JWT_SECRET", ""),
    )


def service_headers(settings: Settings) -> dict[str, str]:
    return {
        "apikey": settings.supabase_service_role_key,
        "Authorization": f"Bearer {settings.supabase_service_role_key}",
        "Content-Type": "application/json",
    }


@pytest_asyncio.fixture
async def api_client(live_settings: Settings) -> AsyncIterator[AsyncClient]:
    app = create_app(settings=live_settings)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def auth(user: LiveUser) -> dict[str, str]:
    return {"Authorization": f"Bearer {user.token}"}


@pytest_asyncio.fixture
async def make_user(live_settings: Settings) -> AsyncIterator[UserFactory]:
    created: list[str] = []

    async with httpx.AsyncClient(timeout=15) as http:
        async def factory(prefix: str) -> LiveUser:
            email = f"e2e-api-{prefix}-{uuid4().hex[:8]}@example.com"
            response = await http.post(
                f"{live_settings.supabase_url}/auth/v1/admin/users",
                headers=service_headers(live_settings),
                json={"email": email, "password": PASSWORD, "email_confirm": True},
            )
            response.raise_for_status()
            user_id = response.json()["id"]
            created.append(user_id)

            token_response = await http.post(
                f"{live_settings.supabase_url}/auth/v1/token?grant_type=password",
                headers={
                    "apikey": live_settings.supabase_anon_key,
                    "Content-Type": "application/json",
                },
                json={"email": email, "password": PASSWORD},
            )
            token_response.raise_for_status()
            return LiveUser(id=user_id, email=email, token=token_response.json()["access_token"])

        yield factory

        # Deleting the household cascades memberships and receipts; then remove
        # the auth users so repeated runs start clean.
        if created:
            ids = ",".join(created)
            households = await http.get(
                f"{live_settings.supabase_url}/rest/v1/households?select=id&created_by=in.({ids})",
                headers=service_headers(live_settings),
            )
            if households.status_code == 200:
                for row in households.json():
                    await http.delete(
                        f"{live_settings.supabase_url}/rest/v1/households?id=eq.{row['id']}",
                        headers=service_headers(live_settings),
                    )
            for user_id in created:
                await http.delete(
                    f"{live_settings.supabase_url}/auth/v1/admin/users/{user_id}",
                    headers=service_headers(live_settings),
                )
