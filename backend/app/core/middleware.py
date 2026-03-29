"""Request ID middleware for tracing."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.errors import SmartKalError

REQUEST_ID_HEADER = "X-Request-ID"

logger: structlog.stdlib.BoundLogger = structlog.get_logger()


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Injects a unique request ID and catches unhandled exceptions."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))
        request.state.request_id = request_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        try:
            response = await call_next(request)
        except SmartKalError as exc:
            # SmartKalError that escaped the exception handler layer
            await logger.awarning(
                "smartkal_error",
                error_code=exc.error_code,
                status_code=exc.status_code,
            )
            response = JSONResponse(
                status_code=exc.status_code,
                content=exc.to_dict(request_id=request_id),
            )
        except Exception as exc:
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
            response = JSONResponse(status_code=500, content=body)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
