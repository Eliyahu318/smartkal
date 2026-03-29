"""Tests for the error handling system (US-006)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.errors import (
    AuthenticationError,
    ClaudeAPIError,
    DatabaseError,
    ExternalServiceError,
    NotFoundError,
    RateLimitError,
    ReceiptParsingError,
    SmartKalError,
    SuperGETError,
    ValidationError,
)
from app.core.middleware import REQUEST_ID_HEADER


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---- Unit tests for error classes ----


ERROR_CLASSES: list[tuple[type[SmartKalError], int, str]] = [
    (SmartKalError, 500, "אירעה שגיאה"),
    (ValidationError, 422, "הנתונים שהוזנו אינם תקינים"),
    (AuthenticationError, 401, "נדרשת התחברות"),
    (NotFoundError, 404, "הפריט לא נמצא"),
    (RateLimitError, 429, "יותר מדי בקשות, נסה שוב מאוחר יותר"),
    (ExternalServiceError, 502, "שגיאה בשירות חיצוני"),
    (ReceiptParsingError, 422, "לא ניתן לעבד את הקבלה"),
    (ClaudeAPIError, 502, "שגיאה בשירות Claude AI"),
    (SuperGETError, 502, "שגיאה בשירות השוואת מחירים"),
    (DatabaseError, 500, "שגיאת מסד נתונים"),
]


@pytest.mark.parametrize(
    "error_cls, expected_status, expected_he",
    ERROR_CLASSES,
    ids=[cls.__name__ for cls, _, _ in ERROR_CLASSES],
)
def test_error_status_code_and_hebrew_message(
    error_cls: type[SmartKalError], expected_status: int, expected_he: str
) -> None:
    exc = error_cls()
    assert exc.status_code == expected_status
    assert exc.message_he == expected_he


def test_error_to_dict_structure() -> None:
    exc = NotFoundError(
        message_en="User not found",
        details={"user_id": "abc"},
    )
    body = exc.to_dict(request_id="req-123")
    error = body["error"]

    assert error["code"] == "NOT_FOUND"
    assert error["message"] == "הפריט לא נמצא"
    assert error["message_en"] == "User not found"
    assert error["details"] == {"user_id": "abc"}
    assert error["debug"]["request_id"] == "req-123"
    assert "timestamp" in error["debug"]
    assert "source" in error["debug"]


def test_error_custom_hebrew_message() -> None:
    exc = ValidationError(message_he="שם המוצר חסר")
    assert exc.message_he == "שם המוצר חסר"


def test_error_source_location_captured() -> None:
    exc = SmartKalError()
    # Should contain this test file path and a line number
    assert "test_errors.py:" in exc.source_location


# ---- Integration tests via the FastAPI app ----


def _create_test_app():
    """Create a fresh app with test routes that raise various errors."""
    from fastapi import FastAPI

    from app.core.exception_handlers import register_exception_handlers
    from app.core.middleware import RequestIDMiddleware

    test_app = FastAPI()
    test_app.add_middleware(RequestIDMiddleware)
    register_exception_handlers(test_app)

    @test_app.get("/raise-not-found")
    async def raise_not_found():
        raise NotFoundError(message_en="Item gone", details={"id": "123"})

    @test_app.get("/raise-auth")
    async def raise_auth():
        raise AuthenticationError()

    @test_app.get("/raise-validation")
    async def raise_validation():
        raise ValidationError(message_he="שדה חובה חסר")

    @test_app.get("/raise-rate-limit")
    async def raise_rate_limit():
        raise RateLimitError()

    @test_app.get("/raise-unhandled")
    async def raise_unhandled():
        raise RuntimeError("something unexpected")

    return test_app


@pytest.mark.anyio
async def test_not_found_error_response() -> None:
    app = _create_test_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-not-found")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["message"] == "הפריט לא נמצא"
    assert body["error"]["details"] == {"id": "123"}


@pytest.mark.anyio
async def test_auth_error_response() -> None:
    app = _create_test_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-auth")

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "AUTHENTICATION_ERROR"
    assert resp.json()["error"]["message"] == "נדרשת התחברות"


@pytest.mark.anyio
async def test_validation_error_with_custom_hebrew() -> None:
    app = _create_test_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-validation")

    assert resp.status_code == 422
    assert resp.json()["error"]["message"] == "שדה חובה חסר"


@pytest.mark.anyio
async def test_rate_limit_error_response() -> None:
    app = _create_test_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-rate-limit")

    assert resp.status_code == 429


@pytest.mark.anyio
async def test_unhandled_exception_returns_500() -> None:
    app = _create_test_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-unhandled")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert body["error"]["message"] == "שגיאה פנימית בשרת"


@pytest.mark.anyio
async def test_request_id_in_response_header() -> None:
    app = _create_test_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/raise-not-found")

    assert REQUEST_ID_HEADER in resp.headers
    request_id = resp.headers[REQUEST_ID_HEADER]
    # Also present in the error body
    assert resp.json()["error"]["debug"]["request_id"] == request_id


@pytest.mark.anyio
async def test_request_id_passthrough() -> None:
    """When client sends X-Request-ID, server should echo it back."""
    app = _create_test_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(
            "/raise-not-found", headers={REQUEST_ID_HEADER: "my-trace-id"}
        )

    assert resp.headers[REQUEST_ID_HEADER] == "my-trace-id"
    assert resp.json()["error"]["debug"]["request_id"] == "my-trace-id"


@pytest.mark.anyio
async def test_health_still_works() -> None:
    """Verify the real app still serves health after error handling is wired in."""
    from app.main import app as real_app

    transport = ASGITransport(app=real_app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert REQUEST_ID_HEADER in resp.headers
