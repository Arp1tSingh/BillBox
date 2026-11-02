"""Supabase JWT verification.

Supabase projects use either legacy HS256 tokens or asymmetric keys exposed via
JWKS. Both paths are supported; the verifier checks issuer, audience, expiry and
subject, and caches signing keys through PyJWT's `PyJWKClient`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

import anyio
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from app.config import Settings, get_settings
from app.domain import AuthUser
from app.errors import AppError, AuthError

logger = logging.getLogger(__name__)
_bearer = HTTPBearer(auto_error=False)


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> AuthUser: ...


@dataclass
class SupabaseJWTVerifier:
    settings: Settings
    _jwks_client: PyJWKClient | None = None

    def __post_init__(self) -> None:
        if not self.settings.supabase_jwt_secret:
            self._jwks_client = PyJWKClient(self.settings.jwks_url, cache_keys=True)

    async def verify(self, token: str) -> AuthUser:
        try:
            return await anyio.to_thread.run_sync(self._verify_sync, token)
        except AppError:
            raise
        except jwt.ExpiredSignatureError as exc:
            raise AuthError("Your session expired. Sign in again.", "session_expired") from exc
        except jwt.PyJWTError as exc:
            logger.info("jwt_rejected", extra={"reason": type(exc).__name__})
            raise AuthError("Your session is not valid. Sign in again.") from exc
        except Exception as exc:  # JWKS fetch / network failure
            logger.warning("jwt_verification_failed", extra={"reason": type(exc).__name__})
            raise AuthError("Could not verify your session. Try again.") from exc

    def _verify_sync(self, token: str) -> AuthUser:
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg", "")
        options = {"require": ["exp", "iss", "aud", "sub"]}
        kwargs = {
            "audience": "authenticated",
            "issuer": self.settings.issuer,
            "options": options,
        }

        if algorithm == "HS256":
            if not self.settings.supabase_jwt_secret:
                raise AuthError("This project does not accept HS256 sessions.")
            payload = jwt.decode(
                token,
                self.settings.supabase_jwt_secret,
                algorithms=["HS256"],
                **kwargs,
            )
        elif algorithm in {"RS256", "ES256", "EdDSA"}:
            if self._jwks_client is None:
                self._jwks_client = PyJWKClient(self.settings.jwks_url, cache_keys=True)
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[algorithm],
                **kwargs,
            )
        else:
            raise AuthError("Unsupported session signing algorithm.")

        try:
            user_id = UUID(payload["sub"])
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthError("Your session has no valid user id.") from exc

        return AuthUser(
            id=user_id,
            email=payload.get("email"),
            role=payload.get("role"),
        )


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    settings: Settings = Depends(get_settings),
) -> AuthUser:
    if credentials is None or not credentials.credentials:
        raise AuthError()
    verifier: TokenVerifier | None = getattr(request.app.state, "jwt_verifier", None)
    if verifier is None:
        verifier = SupabaseJWTVerifier(settings)
    return await verifier.verify(credentials.credentials)
