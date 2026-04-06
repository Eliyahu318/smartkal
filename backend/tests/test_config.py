"""Tests for Settings configuration — cookie_secure derivation from environment.

Verifies that cookie_secure is automatically derived from the environment
setting when not explicitly provided, ensuring secure defaults in production
and HTTP-compatible defaults in development.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


class TestCookieSecureDerivation:
    """Test cookie_secure field is correctly derived from environment."""

    def test_development_defaults_to_insecure(self) -> None:
        """In development (default), cookie_secure should be False for HTTP."""
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(
                database_url="postgresql+asyncpg://localhost/test",
                environment="development",
            )

        assert settings.cookie_secure is False

    def test_production_defaults_to_secure(self) -> None:
        """In production, cookie_secure should be True for HTTPS."""
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(
                database_url="postgresql+asyncpg://localhost/test",
                environment="production",
            )

        assert settings.cookie_secure is True

    def test_explicit_override_respected_in_production(self) -> None:
        """Explicit cookie_secure=False overrides production default."""
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(
                database_url="postgresql+asyncpg://localhost/test",
                environment="production",
                cookie_secure=False,
            )

        assert settings.cookie_secure is False

    def test_explicit_override_respected_in_development(self) -> None:
        """Explicit cookie_secure=True overrides development default."""
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(
                database_url="postgresql+asyncpg://localhost/test",
                environment="development",
                cookie_secure=True,
            )

        assert settings.cookie_secure is True

    def test_default_environment_is_development(self) -> None:
        """When no environment is set, defaults to development (insecure cookies)."""
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            settings = Settings(
                database_url="postgresql+asyncpg://localhost/test",
            )

        assert settings.environment == "development"
        assert settings.cookie_secure is False

    def test_is_production_property(self) -> None:
        """is_production property correctly reflects environment."""
        from app.config import Settings

        with patch.dict("os.environ", {}, clear=True):
            dev = Settings(
                database_url="postgresql+asyncpg://localhost/test",
                environment="development",
            )
            prod = Settings(
                database_url="postgresql+asyncpg://localhost/test",
                environment="production",
            )

        assert dev.is_production is False
        assert prod.is_production is True
