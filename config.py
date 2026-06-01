from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core Flask
    secret_key: str = Field(default="dev-secret-change-me")
    flask_env: str = Field(default="development")

    # Database
    database_url: str = Field(default="sqlite:///wc2026.db")

    # App behaviour
    invite_code: str = Field(default="wc2026")
    lock_minutes_before: int = Field(default=60)
    admin_email: str = Field(default="")

    # Internationalisation
    babel_default_locale: str = "en"
    babel_supported_locales: list[str] = ["en", "pl"]

    # External API
    football_data_api_key: str = Field(default="")
    football_data_base_url: str = "https://api.football-data.org/v4"

    @property
    def sqlalchemy_database_uri(self) -> str:
        # SQLAlchemy 2.x requires postgresql:// not postgres:// (Supabase uses the latter)
        url = self.database_url
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    @property
    def debug(self) -> bool:
        return self.flask_env == "development"

    @property
    def testing(self) -> bool:
        return self.flask_env == "testing"


class DevelopmentSettings(Settings):
    flask_env: str = "development"


class ProductionSettings(Settings):
    flask_env: str = "production"


class TestingSettings(Settings):
    model_config = SettingsConfigDict(env_file=None)  # never read .env in tests

    flask_env: str = "testing"
    database_url: str = "sqlite:///:memory:"
    wtf_csrf_enabled: bool = False
    secret_key: str = "test-secret"


@lru_cache(maxsize=1)
def get_config() -> Settings:
    import os

    env = os.getenv("FLASK_ENV", "development")
    match env:
        case "production":
            return ProductionSettings()
        case "testing":
            return TestingSettings()
        case _:
            return DevelopmentSettings()
