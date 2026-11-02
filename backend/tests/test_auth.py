from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from app.auth import SupabaseJWTVerifier
from app.config import Settings
from app.errors import AuthError


def make_settings(secret: str = "test-secret-that-is-at-least-32-chars-long") -> Settings:
    return Settings(
        environment="test",
        supabase_url="http://supabase.test",
        supabase_jwt_secret=secret,
    )


def make_token(settings: Settings, **overrides: object) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {
        "sub": str(uuid4()),
        "aud": "authenticated",
        "iss": settings.issuer,
        "exp": now + timedelta(minutes=5),
        "iat": now,
        "email": "person@example.com",
        "role": "authenticated",
    }
    payload.update(overrides)
    return jwt.encode(payload, settings.supabase_jwt_secret, algorithm="HS256")


async def test_hs256_token_is_accepted() -> None:
    settings = make_settings()
    token = make_token(settings)
    user = await SupabaseJWTVerifier(settings).verify(token)
    assert user.email == "person@example.com"


async def test_expired_token_is_rejected() -> None:
    settings = make_settings()
    token = make_token(settings, exp=datetime.now(UTC) - timedelta(minutes=1))
    with pytest.raises(AuthError):
        await SupabaseJWTVerifier(settings).verify(token)


async def test_wrong_audience_is_rejected() -> None:
    settings = make_settings()
    token = make_token(settings, aud="service_role")
    with pytest.raises(AuthError):
        await SupabaseJWTVerifier(settings).verify(token)


async def test_wrong_issuer_is_rejected() -> None:
    settings = make_settings()
    token = make_token(settings, iss="http://elsewhere.test/auth/v1")
    with pytest.raises(AuthError):
        await SupabaseJWTVerifier(settings).verify(token)


async def test_missing_subject_is_rejected() -> None:
    settings = make_settings()
    token = make_token(settings, sub=None)
    with pytest.raises(AuthError):
        await SupabaseJWTVerifier(settings).verify(token)
