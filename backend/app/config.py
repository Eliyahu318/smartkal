from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/smartkal"

    # JWT
    jwt_secret: str = "change-me-to-a-random-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Google OAuth
    google_client_id: str = ""

    # Anthropic Claude API
    anthropic_api_key: str = ""

    # SuperGET API
    superget_api_key: str = ""

    # CORS
    cors_origins: str = "http://localhost:5173"

    # Cookies — derived from environment by default (see _derive_defaults)
    cookie_secure: bool | None = None

    # Environment
    environment: str = "development"

    @model_validator(mode="after")
    def _derive_defaults(self) -> "Settings":
        """Derive cookie_secure from environment when not explicitly set.

        Development (HTTP) → Secure=False; Production (HTTPS) → Secure=True.
        Explicit COOKIE_SECURE env var overrides this derivation.
        """
        if self.cookie_secure is None:
            self.cookie_secure = self.is_production
        return self

    @property
    def async_database_url(self) -> str:
        """Normalize DATABASE_URL for asyncpg (Render provides postgresql://)."""
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def get_settings() -> Settings:
    return Settings()
