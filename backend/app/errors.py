"""Error types and the single JSON error envelope used by the API."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """An expected failure that maps to an HTTP response."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

    def body(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details,
            }
        }


class AuthError(AppError):
    def __init__(self, message: str = "Sign in to continue.", code: str = "unauthorized") -> None:
        super().__init__(401, code, message)


class ForbiddenError(AppError):
    def __init__(
        self, message: str = "You do not have access to that.", code: str = "forbidden"
    ) -> None:
        super().__init__(403, code, message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found.", code: str = "not_found") -> None:
        super().__init__(404, code, message)


class ConflictError(AppError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(409, code, message)


class ConfigError(AppError):
    def __init__(self, message: str) -> None:
        super().__init__(500, "server_not_configured", message)
