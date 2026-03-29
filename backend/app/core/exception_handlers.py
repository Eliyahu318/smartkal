"""Global exception handlers for FastAPI."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.errors import SmartKalError

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


def _get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


async def smartkal_error_handler(request: Request, exc: SmartKalError) -> JSONResponse:
    """Handle all SmartKalError subclasses."""
    request_id = _get_request_id(request)
    await logger.awarning(
        "smartkal_error",
        error_code=exc.error_code,
        status_code=exc.status_code,
        message=exc.message_en,
        request_id=request_id,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict(request_id=request_id),
    )


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions with a generic error response."""
    request_id = _get_request_id(request)
    await logger.aerror(
        "unhandled_exception",
        error_type=type(exc).__name__,
        error_message=str(exc),
        request_id=request_id,
    )
    body: dict[str, Any] = {
        "error": {
            "code": "INTERNAL_ERROR",
            "message": "שגיאה פנימית בשרת",
            "message_en": "Internal server error",
            "details": {},
            "debug": {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "request_id": request_id,
                "source": "",
            },
        }
    }
    return JSONResponse(status_code=500, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers on the FastAPI app."""
    app.add_exception_handler(SmartKalError, smartkal_error_handler)  # type: ignore[arg-type, unused-ignore]
    app.add_exception_handler(Exception, unhandled_error_handler)  # type: ignore[arg-type, unused-ignore]
