"""Middleware: request ID tracing, security headers, rate limiting."""

from __future__ import annotations

import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.errors import RateLimitError, SmartKalError

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


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to all responses."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; frame-ancestors 'none'"
        )
        return response


class _SlidingWindowCounter:
    """In-memory sliding window rate counter per key."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def is_allowed(self, key: str) -> tuple[bool, int]:
        """Check if request is allowed. Returns (allowed, remaining)."""
        now = time.monotonic()
        cutoff = now - self.window_seconds
        bucket = self._hits[key]

        # Evict expired entries
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        remaining = max(0, self.max_requests - len(bucket))
        if len(bucket) >= self.max_requests:
            return False, 0

        bucket.append(now)
        return True, remaining - 1

    def reset(self) -> None:
        """Clear all tracked state (useful for testing)."""
        self._hits.clear()


# Upload path prefix for stricter rate limiting
_UPLOAD_PATH = "/api/v1/receipts/upload"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Per-IP sliding window rate limiter.

    Two tiers:
    - Upload endpoints: 10 requests per hour
    - General API: 100 requests per minute

    Skips health check and non-API paths.
    """

    def __init__(
        self,
        app: Any,
        *,
        general_max: int = 100,
        general_window: int = 60,
        upload_max: int = 10,
        upload_window: int = 3600,
    ) -> None:
        super().__init__(app)
        self._general = _SlidingWindowCounter(general_max, general_window)
        self._upload = _SlidingWindowCounter(upload_max, upload_window)

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        path = request.url.path

        # Skip non-API paths and health check
        if not path.startswith("/api/") or path == "/health":
            return await call_next(request)

        client_ip = self._get_client_ip(request)

        # Check upload-specific limit first
        if path == _UPLOAD_PATH and request.method == "POST":
            allowed, remaining = self._upload.is_allowed(client_ip)
            if not allowed:
                err = RateLimitError(
                    message_he="חרגת ממגבלת ההעלאות, נסה שוב מאוחר יותר",
                    message_en="Upload rate limit exceeded (10/hour)",
                    details={"retry_after_seconds": self._upload.window_seconds},
                )
                request_id = getattr(request.state, "request_id", "")
                return JSONResponse(
                    status_code=err.status_code,
                    content=err.to_dict(request_id=request_id),
                    headers={"Retry-After": str(self._upload.window_seconds)},
                )

        # Check general limit
        allowed, remaining = self._general.is_allowed(client_ip)
        if not allowed:
            err = RateLimitError(
                details={"retry_after_seconds": self._general.window_seconds},
            )
            request_id = getattr(request.state, "request_id", "")
            return JSONResponse(
                status_code=err.status_code,
                content=err.to_dict(request_id=request_id),
                headers={"Retry-After": str(self._general.window_seconds)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """Extract client IP, respecting X-Forwarded-For behind a proxy."""
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        client = request.client
        return client.host if client else "unknown"
