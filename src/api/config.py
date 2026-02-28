"""
GeoMRV API Configuration
========================
Loads settings from environment variables / .env file.
"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # App
    ENV: str = "dev"
    APP_NAME: str = "geomrv"
    DEBUG: bool = False

    # Database
    POSTGRES_HOST: str
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_SSLMODE: str | None = None
    DATABASE_URL: str | None = None

    # Azure Storage
    AZURE_STORAGE_CONNECTION_STRING: str | None = None
    AZURE_STORAGE_ACCOUNT: str | None = None
    AZURE_STORAGE_ACCOUNT_KEY: str | None = None
    AZURE_STORAGE_CONTAINER_EVIDENCE: str = "evidence-packages"
    AZURE_STORAGE_CONTAINER_CACHE: str = "satellite-data-cache"

    # Satellite / Earth Engine
    GOOGLE_EARTH_ENGINE_CREDENTIALS: str | None = None
    GEE_PROJECT: str | None = None

    # API
    CORS_ORIGINS: list[str] = ["*"]

    @property
    def db_url(self) -> str:
        """Build PostgreSQL connection URL."""
        if self.DATABASE_URL:
            return self.DATABASE_URL

        sslmode = f"?sslmode={self.POSTGRES_SSLMODE}" if self.POSTGRES_SSLMODE else ""
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}{sslmode}"
        )


settings = Settings()
