"""Tests for US-007: Google OAuth + JWT authentication backend."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AuthenticationError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_token_pair,
    decode_token,
    verify_google_token,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


FAKE_GOOGLE_PAYLOAD: dict[str, Any] = {
    "sub": "google-uid-12345",
    "email": "test@example.com",
    "name": "Test User",
    "picture": "https://example.com/photo.jpg",
    "aud": "test-client-id",
    "iss": "accounts.google.com",
    "email_verified": True,
}

SETTINGS_OVERRIDE = {
    "google_client_id": "test-client-id",
    "jwt_secret": "test-secret-key-for-jwt",
    "database_url": "postgresql+asyncpg://test:test@localhost:5432/testdb",
}


def _make_test_app() -> Any:
    """Create a test FastAPI app with mocked DB dependency."""
    from unittest.mock import AsyncMock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from app.api.v1 import api_v1_router
    from app.core.exception_handlers import register_exception_handlers
    from app.db.session import get_db

    app = FastAPI()
    register_exception_handlers(app)
    app.include_router(api_v1_router)
    return app


# ---------------------------------------------------------------------------
# Unit tests: security.py — JWT lifecycle
# ---------------------------------------------------------------------------


class TestJWTLifecycle:
    """Test JWT creation and decoding."""

    def test_create_access_token_is_valid_jwt(self) -> None:
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_create_refresh_token_is_valid_jwt(self) -> None:
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)
        settings = get_settings()
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_create_token_pair_returns_both(self) -> None:
        user_id = uuid.uuid4()
        pair = create_token_pair(user_id)
        assert "access_token" in pair
        assert "refresh_token" in pair
        assert pair["token_type"] == "bearer"

    def test_decode_access_token_succeeds(self) -> None:
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        payload = decode_token(token, expected_type="access")
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "access"

    def test_decode_refresh_token_succeeds(self) -> None:
        user_id = uuid.uuid4()
        token = create_refresh_token(user_id)
        payload = decode_token(token, expected_type="refresh")
        assert payload["sub"] == str(user_id)
        assert payload["type"] == "refresh"

    def test_decode_wrong_type_raises_error(self) -> None:
        user_id = uuid.uuid4()
        token = create_access_token(user_id)
        with pytest.raises(AuthenticationError) as exc_info:
            decode_token(token, expected_type="refresh")
        assert exc_info.value.error_code == "AUTHENTICATION_ERROR"
        assert "token type" in exc_info.value.message_en.lower()

    def test_decode_expired_token_raises_error(self) -> None:
        settings = get_settings()
        payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "type": "access",
            "iat": datetime.now(timezone.utc) - timedelta(hours=2),
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(AuthenticationError) as exc_info:
            decode_token(token, expected_type="access")
        assert exc_info.value.status_code == 401

    def test_decode_invalid_token_raises_error(self) -> None:
        with pytest.raises(AuthenticationError):
            decode_token("not-a-valid-jwt", expected_type="access")

    def test_decode_wrong_secret_raises_error(self) -> None:
        payload = {
            "sub": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(payload, "wrong-secret", algorithm="HS256")
        with pytest.raises(AuthenticationError):
            decode_token(token, expected_type="access")

    def test_decode_token_missing_sub_raises_error(self) -> None:
        settings = get_settings()
        payload = {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "type": "access",
            "iat": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4()),
        }
        token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
        with pytest.raises(AuthenticationError) as exc_info:
            decode_token(token, expected_type="access")
        assert "subject" in exc_info.value.message_en.lower()


# ---------------------------------------------------------------------------
# Unit tests: security.py — Google token verification
# ---------------------------------------------------------------------------


class TestGoogleTokenVerification:
    """Test Google token verification with mocked Google API."""

    @patch("app.core.security.get_settings")
    def test_missing_client_id_raises_error(self, mock_settings: MagicMock) -> None:
        mock_settings.return_value = MagicMock(google_client_id="")
        with pytest.raises(AuthenticationError) as exc_info:
            verify_google_token("some-token")
        assert "not configured" in exc_info.value.message_en.lower()

    @patch("app.core.security.get_settings")
    @patch("app.core.security.google_id_token.verify_oauth2_token")
    def test_valid_google_token_returns_payload(
        self,
        mock_verify: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_settings.return_value = MagicMock(google_client_id="test-client-id")
        mock_verify.return_value = FAKE_GOOGLE_PAYLOAD

        result = verify_google_token("valid-google-token")
        assert result["sub"] == "google-uid-12345"
        assert result["email"] == "test@example.com"
        mock_verify.assert_called_once()

    @patch("app.core.security.get_settings")
    @patch("app.core.security.google_id_token.verify_oauth2_token")
    def test_invalid_google_token_raises_error(
        self,
        mock_verify: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_settings.return_value = MagicMock(google_client_id="test-client-id")
        mock_verify.side_effect = ValueError("Token expired")

        with pytest.raises(AuthenticationError) as exc_info:
            verify_google_token("expired-token")
        assert "invalid google token" in exc_info.value.message_en.lower()

    @patch("app.core.security.get_settings")
    @patch("app.core.security.google_id_token.verify_oauth2_token")
    def test_google_token_missing_sub_raises_error(
        self,
        mock_verify: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_settings.return_value = MagicMock(google_client_id="test-client-id")
        mock_verify.return_value = {"email": "test@example.com"}  # no "sub"

        with pytest.raises(AuthenticationError) as exc_info:
            verify_google_token("token-without-sub")
        assert "missing" in exc_info.value.message_en.lower()

    @patch("app.core.security.get_settings")
    @patch("app.core.security.google_id_token.verify_oauth2_token")
    def test_google_token_missing_email_raises_error(
        self,
        mock_verify: MagicMock,
        mock_settings: MagicMock,
    ) -> None:
        mock_settings.return_value = MagicMock(google_client_id="test-client-id")
        mock_verify.return_value = {"sub": "123"}  # no "email"

        with pytest.raises(AuthenticationError):
            verify_google_token("token-without-email")


# ---------------------------------------------------------------------------
# Integration tests: auth endpoints
# ---------------------------------------------------------------------------


class TestAuthEndpoints:
    """Test auth API endpoints with mocked DB and Google verification."""

    @pytest.mark.anyio
    @patch("app.api.v1.auth.verify_google_token")
    @patch("app.api.v1.auth.seed_categories_for_user")
    async def test_google_login_creates_new_user(
        self,
        mock_seed: AsyncMock,
        mock_google: MagicMock,
    ) -> None:
        """POST /api/v1/auth/google with new user creates account and returns tokens."""
        mock_google.return_value = FAKE_GOOGLE_PAYLOAD
        mock_seed.return_value = []

        fake_user_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # No existing user

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        # On flush, assign an id to the User object that was added
        added_objects: list[Any] = []

        def capture_add(obj: Any) -> None:
            added_objects.append(obj)
            obj.id = fake_user_id

        mock_session.add.side_effect = capture_add
        mock_session.flush = AsyncMock()

        from app.db.session import get_db

        async def fake_get_db():  # type: ignore[no-untyped-def]
            yield mock_session

        app = _make_test_app()
        app.dependency_overrides[get_db] = fake_get_db

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/google",
                json={"id_token": "valid-google-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify a User was added to the session
        assert len(added_objects) == 1
        assert added_objects[0].email == "test@example.com"

        # Verify the access token is decodable
        payload = decode_token(data["access_token"], expected_type="access")
        assert payload["sub"] == str(fake_user_id)

    @pytest.mark.anyio
    @patch("app.api.v1.auth.verify_google_token")
    async def test_google_login_existing_user(
        self,
        mock_google: MagicMock,
    ) -> None:
        """POST /api/v1/auth/google with existing user returns tokens without seeding."""
        mock_google.return_value = FAKE_GOOGLE_PAYLOAD

        fake_user_id = uuid.uuid4()
        mock_user = MagicMock()
        mock_user.id = fake_user_id
        mock_user.email = "test@example.com"
        mock_user.name = "Old Name"
        mock_user.google_sub = "google-uid-12345"
        mock_user.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user  # Existing user

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        from app.db.session import get_db

        async def fake_get_db():  # type: ignore[no-untyped-def]
            yield mock_session

        app = _make_test_app()
        app.dependency_overrides[get_db] = fake_get_db

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/google",
                json={"id_token": "valid-google-token"},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

        # Verify user name was updated
        assert mock_user.name == "Test User"

    @pytest.mark.anyio
    async def test_google_login_empty_token_returns_422(self) -> None:
        """POST /api/v1/auth/google with empty token returns validation error."""
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/google",
                json={"id_token": ""},
            )
        assert response.status_code == 422

    @pytest.mark.anyio
    async def test_refresh_with_valid_token(self) -> None:
        """POST /api/v1/auth/refresh with valid refresh token returns new pair."""
        fake_user_id = uuid.uuid4()
        refresh = create_refresh_token(fake_user_id)

        mock_user = MagicMock()
        mock_user.id = fake_user_id
        mock_user.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        from app.db.session import get_db

        async def fake_get_db():  # type: ignore[no-untyped-def]
            yield mock_session

        app = _make_test_app()
        app.dependency_overrides[get_db] = fake_get_db

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh},
            )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    @pytest.mark.anyio
    async def test_refresh_with_access_token_fails(self) -> None:
        """POST /api/v1/auth/refresh with access token (wrong type) returns 401."""
        fake_user_id = uuid.uuid4()
        access = create_access_token(fake_user_id)

        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": access},
            )

        assert response.status_code == 401
        data = response.json()
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"

    @pytest.mark.anyio
    async def test_refresh_with_invalid_token_fails(self) -> None:
        """POST /api/v1/auth/refresh with garbage token returns 401."""
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": "garbage-token"},
            )
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_refresh_with_deactivated_user_fails(self) -> None:
        """POST /api/v1/auth/refresh for deactivated user returns 401."""
        fake_user_id = uuid.uuid4()
        refresh = create_refresh_token(fake_user_id)

        mock_user = MagicMock()
        mock_user.id = fake_user_id
        mock_user.is_active = False  # Deactivated

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        from app.db.session import get_db

        async def fake_get_db():  # type: ignore[no-untyped-def]
            yield mock_session

        app = _make_test_app()
        app.dependency_overrides[get_db] = fake_get_db

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/v1/auth/refresh",
                json={"refresh_token": refresh},
            )
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_me_without_token_returns_401(self) -> None:
        """GET /api/v1/auth/me without Authorization header returns 401."""
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_me_with_invalid_token_returns_401(self) -> None:
        """GET /api/v1/auth/me with invalid token returns 401."""
        app = _make_test_app()
        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": "Bearer garbage-token"},
            )
        assert response.status_code == 401

    @pytest.mark.anyio
    async def test_me_with_valid_token_returns_user(self) -> None:
        """GET /api/v1/auth/me with valid access token returns user profile."""
        fake_user_id = uuid.uuid4()
        access = create_access_token(fake_user_id)

        mock_user = MagicMock()
        mock_user.id = fake_user_id
        mock_user.email = "test@example.com"
        mock_user.name = "Test User"
        mock_user.picture_url = "https://example.com/photo.jpg"
        mock_user.is_active = True

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        mock_session = AsyncMock(spec=AsyncSession)
        mock_session.execute.return_value = mock_result

        from app.db.session import get_db

        async def fake_get_db():  # type: ignore[no-untyped-def]
            yield mock_session

        app = _make_test_app()
        app.dependency_overrides[get_db] = fake_get_db

        transport = ASGITransport(app=app)  # type: ignore[arg-type]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/auth/me",
                headers={"Authorization": f"Bearer {access}"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["name"] == "Test User"
        assert data["id"] == str(fake_user_id)
