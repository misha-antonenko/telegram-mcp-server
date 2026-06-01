from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    api_id: int
    api_hash: str
    session_string: str
    image_cache_dir: Path = Path(".image_cache")
    mcp_auth_token: str | None = None
    mcp_host: str = "0.0.0.0"
    mcp_port: int = 8000
    mcp_transport: str = "http"
    mcp_domain: str | None = None
    mcp_external_port: int | None = None
    github_client_id: str | None = None
    github_client_secret: str | None = None
    github_jwt_signing_key: str | None = None
    oauth_storage_dir: Path = Path(".oauth_storage")


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
