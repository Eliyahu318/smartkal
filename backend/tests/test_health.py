from collections.abc import AsyncIterator

from httpx import ASGITransport, AsyncClient

import pytest

from app.main import app, get_db_health


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.mark.anyio
async def test_health_returns_ok(client: AsyncClient) -> None:
    """Liveness never touches the DB and always reports ok when the app is up."""
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_readiness_returns_200_when_db_reachable(client: AsyncClient) -> None:
    """Readiness reports 200 when the DB probe succeeds."""
    app.dependency_overrides[get_db_health] = lambda: {"status": "ready", "database": "ok"}

    response = await client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "database": "ok"}


@pytest.mark.anyio
async def test_readiness_returns_503_when_db_unreachable(client: AsyncClient) -> None:
    """Readiness reports 503 (not a false 200) when the DB is down."""
    app.dependency_overrides[get_db_health] = lambda: {
        "status": "not_ready",
        "database": "unreachable",
    }

    response = await client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready", "database": "unreachable"}
