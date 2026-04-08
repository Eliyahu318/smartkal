"""Tests for rate limiting middleware (US-029)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.middleware import RateLimitMiddleware, _SlidingWindowCounter
from app.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


# ---- Unit tests for _SlidingWindowCounter ----


class TestSlidingWindowCounter:
    def test_allows_within_limit(self) -> None:
        counter = _SlidingWindowCounter(max_requests=3, window_seconds=60)
        allowed, remaining = counter.is_allowed("ip1")
        assert allowed is True
        assert remaining == 2

    def test_blocks_after_limit(self) -> None:
        counter = _SlidingWindowCounter(max_requests=3, window_seconds=60)
        for _ in range(3):
            counter.is_allowed("ip1")
        allowed, remaining = counter.is_allowed("ip1")
        assert allowed is False
        assert remaining == 0

    def test_separate_keys_independent(self) -> None:
        counter = _SlidingWindowCounter(max_requests=1, window_seconds=60)
        allowed1, _ = counter.is_allowed("ip1")
        allowed2, _ = counter.is_allowed("ip2")
        assert allowed1 is True
        assert allowed2 is True

    def test_reset_clears_state(self) -> None:
        counter = _SlidingWindowCounter(max_requests=1, window_seconds=60)
        counter.is_allowed("ip1")
        counter.reset()
        allowed, _ = counter.is_allowed("ip1")
        assert allowed is True


# ---- Integration tests with the app ----


def _make_rate_limit_app(
    general_max: int = 5,
    general_window: int = 60,
    upload_max: int = 2,
    upload_window: int = 3600,
) -> object:
    """Build a minimal FastAPI app with explicit rate limits and a public endpoint."""
    from fastapi import FastAPI
    from app.core.exception_handlers import register_exception_handlers
    from app.core.middleware import RequestIDMiddleware

    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)
    app.add_middleware(
        RateLimitMiddleware,
        general_max=general_max,
        general_window=general_window,
        upload_max=upload_max,
        upload_window=upload_window,
    )
    register_exception_handlers(app)

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"status": "pong"}

    @app.post("/api/v1/receipts/upload")
    async def fake_upload() -> dict[str, str]:
        return {"status": "ok"}

    return app


@pytest.mark.anyio
async def test_health_bypasses_rate_limit() -> None:
    """Health check should never be rate limited."""
    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(150):
            resp = await client.get("/health")
            assert resp.status_code == 200


@pytest.mark.anyio
async def test_general_rate_limit_returns_429() -> None:
    """Exceeding general API limit returns 429."""
    app = _make_rate_limit_app(general_max=5)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(5):
            await client.get("/api/v1/ping")
        resp = await client.get("/api/v1/ping")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT"
        assert "retry_after_seconds" in body["error"]["details"]


@pytest.mark.anyio
async def test_rate_limit_header_present() -> None:
    """Successful responses include X-RateLimit-Remaining header."""
    app = _make_rate_limit_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/ping")
        assert resp.status_code == 200
        assert "X-RateLimit-Remaining" in resp.headers


@pytest.mark.anyio
async def test_upload_rate_limit() -> None:
    """Upload endpoint has stricter rate limit (10/hour)."""
    app = _make_rate_limit_app(upload_max=2)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(2):
            await client.post("/api/v1/receipts/upload")
        resp = await client.post("/api/v1/receipts/upload")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT"
        assert "העלאות" in body["error"]["message"]


@pytest.mark.anyio
async def test_rate_limit_hebrew_message() -> None:
    """Rate limit error returns Hebrew message."""
    app = _make_rate_limit_app(general_max=3)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(3):
            await client.get("/api/v1/ping")
        resp = await client.get("/api/v1/ping")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["message"]  # Non-empty Hebrew message


@pytest.mark.anyio
async def test_different_ips_independent() -> None:
    """Different IPs have independent rate limit counters."""
    app = _make_rate_limit_app(general_max=5)
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(5):
            await client.get(
                "/api/v1/ping", headers={"X-Forwarded-For": "1.2.3.4"}
            )
        resp = await client.get(
            "/api/v1/ping", headers={"X-Forwarded-For": "1.2.3.4"}
        )
        assert resp.status_code == 429

        resp = await client.get(
            "/api/v1/ping", headers={"X-Forwarded-For": "5.6.7.8"}
        )
        assert resp.status_code == 200
