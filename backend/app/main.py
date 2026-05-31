from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.v1 import api_v1_router
from app.config import get_settings
from app.db.session import engine
from app.core.exception_handlers import register_exception_handlers
from app.core.logging import setup_logging
from app.core.middleware import (
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


async def get_db_health() -> dict[str, str]:
    """Probe database connectivity with a trivial `SELECT 1`.

    Used by the readiness endpoint. Returns a status dict and never raises, so a
    DB outage surfaces as a clean 503 rather than a 500. Defined as a dependency
    so tests can override it via `app.dependency_overrides`.

    Returns:
        ``{"status": "ready", "database": "ok"}`` when the query succeeds,
        otherwise ``{"status": "not_ready", "database": "unreachable"}``.
    """
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await logger.aerror("readiness_db_check_failed", exc_info=True)
        return {"status": "not_ready", "database": "unreachable"}
    return {"status": "ready", "database": "ok"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    json_output = settings.is_production
    setup_logging(json_output=json_output)
    await logger.ainfo("smartkal_starting", environment=settings.environment)
    yield
    await logger.ainfo("smartkal_shutting_down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="SmartKal API",
        version="0.1.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Middleware (order matters: first added = outermost)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)
    if settings.is_production:
        app.add_middleware(RateLimitMiddleware)
    else:
        app.add_middleware(RateLimitMiddleware, general_max=1000, general_window=60)
    app.add_middleware(SecurityHeadersMiddleware)

    # Exception handlers
    register_exception_handlers(app)

    # API routes
    app.include_router(api_v1_router)

    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Liveness probe: the process is up and serving HTTP.

        Intentionally does NOT touch the database — this is the signal an
        orchestrator uses to decide the container is alive. For "can it actually
        serve requests?" use /health/ready.
        """
        return {"status": "ok"}

    @app.get("/health/ready")
    async def readiness_check(
        health: dict[str, str] = Depends(get_db_health),
    ) -> JSONResponse:
        """Readiness probe: 200 when the database is reachable, 503 otherwise.

        Unlike /health, this executes a real query, so external uptime monitors
        see the true serving state instead of a process-is-up false positive.
        """
        status_code = 200 if health["status"] == "ready" else 503
        return JSONResponse(status_code=status_code, content=health)

    return app


app = create_app()
