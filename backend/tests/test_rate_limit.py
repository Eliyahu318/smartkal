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


def _get_app_with_limits(
    general_max: int = 100,
    general_window: int = 60,
    upload_max: int = 10,
    upload_window: int = 3600,
) -> object:
    """Create app and replace RateLimitMiddleware with custom limits."""
    app = create_app()
    # Find and reconfigure the rate limit middleware
    for middleware in app.middleware_stack.__dict__.get("app", app).__dict__.values():
        if isinstance(middleware, RateLimitMiddleware):
            middleware._general = _SlidingWindowCounter(general_max, general_window)
            middleware._upload = _SlidingWindowCounter(upload_max, upload_window)
            break
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
    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust the general limit (default 100/min)
        for _ in range(100):
            await client.get("/api/v1/categories")
        # 101st should be 429
        resp = await client.get("/api/v1/categories")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT"
        assert "retry_after_seconds" in body["error"]["details"]


@pytest.mark.anyio
async def test_rate_limit_header_present() -> None:
    """Successful responses include X-RateLimit-Remaining header."""
    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/categories")
        # May be 401 (unauthenticated) but rate limit header should still be present
        assert "X-RateLimit-Remaining" in resp.headers


@pytest.mark.anyio
async def test_upload_rate_limit() -> None:
    """Upload endpoint has stricter rate limit (10/hour)."""
    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust upload limit (10/hour)
        for _ in range(10):
            await client.post("/api/v1/receipts/upload")
        # 11th should be 429 with upload-specific message
        resp = await client.post("/api/v1/receipts/upload")
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"]["code"] == "RATE_LIMIT"
        assert "העלאות" in body["error"]["message"]


@pytest.mark.anyio
async def test_rate_limit_hebrew_message() -> None:
    """Rate limit error returns Hebrew message."""
    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for _ in range(100):
            await client.get("/api/v1/categories")
        resp = await client.get("/api/v1/categories")
        assert resp.status_code == 429
        body = resp.json()
        # Default Hebrew message from RateLimitError
        assert body["error"]["message"]  # Non-empty Hebrew message


@pytest.mark.anyio
async def test_different_ips_independent() -> None:
    """Different IPs have independent rate limit counters."""
    app = create_app()
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Exhaust limit from one IP
        for _ in range(100):
            await client.get(
                "/api/v1/categories", headers={"X-Forwarded-For": "1.2.3.4"}
            )
        # Same IP blocked
        resp = await client.get(
            "/api/v1/categories", headers={"X-Forwarded-For": "1.2.3.4"}
        )
        assert resp.status_code == 429

        # Different IP still allowed
        resp = await client.get(
            "/api/v1/categories", headers={"X-Forwarded-For": "5.6.7.8"}
        )
        assert resp.status_code != 429
