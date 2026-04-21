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


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
