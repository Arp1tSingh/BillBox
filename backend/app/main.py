"""FastAPI application factory."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.auth import SupabaseJWTVerifier, TokenVerifier
from app.config import Settings, get_settings
from app.errors import AppError
from app.repositories.base import HouseholdsRepository
from app.repositories.supabase_households import SupabaseHouseholdsRepository
from app.routers.households import router as households_router
from app.schemas.households import HealthView
from app.services.households import HouseholdService

logger = logging.getLogger(__name__)


def create_app(
    *,
    settings: Settings | None = None,
    households_repo: HouseholdsRepository | None = None,
    jwt_verifier: TokenVerifier | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    repo = households_repo or SupabaseHouseholdsRepository(
        settings.supabase_url, settings.supabase_service_role_key
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=None if settings.is_production else "/docs",
        redoc_url=None,
        openapi_url=None if settings.is_production else "/openapi.json",
    )
    app.state.settings = settings
    app.state.household_service = HouseholdService(
        repo,
        max_members=settings.max_household_members,
        invite_length=settings.invite_code_length,
    )
    app.state.jwt_verifier = jwt_verifier or SupabaseJWTVerifier(settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Household-Id"],
        max_age=600,
    )

    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return JSONResponse(status_code=exc.status_code, content=exc.body(), headers=headers)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Some fields need attention.",
                    "details": {"errors": jsonable_encoder(exc.errors())},
                }
            },
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled_error", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Something went wrong. Try again.",
                    "details": {},
                }
            },
        )

    @app.get("/health", response_model=HealthView, tags=["ops"])
    async def health() -> HealthView:
        return HealthView(
            status="ok",
            service=settings.app_name,
            environment=settings.environment,
        )

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {"name": settings.app_name, "status": "ok"}

    app.include_router(households_router)
    return app


app = create_app()
