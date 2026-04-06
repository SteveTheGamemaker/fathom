from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8989
    base_url: str = ""


class DatabaseConfig(BaseModel):
    path: str = "./data/fathom.db"


class LLMConfig(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    api_key: str = ""
    model: str = "gpt-4o-mini"
    max_batch_size: int = 30


class MediaConfig(BaseModel):
    root_folders_movies: list[str] = Field(default_factory=lambda: ["/movies"])
    root_folders_series: list[str] = Field(default_factory=lambda: ["/tv"])
    rename_movies: str = "{title} ({year})/{title} ({year}) - {quality}.{ext}"
    rename_episodes: str = (
        "{series}/Season {season:02}/{series} - S{season:02}E{episode:02}"
        " - {episode_title}.{ext}"
    )


class SchedulerConfig(BaseModel):
    rss_sync_interval_minutes: int = 15
    search_missing_interval_hours: int = 6
    import_check_interval_seconds: int = 60


class TMDBConfig(BaseModel):
    api_key: str = ""


class NotificationConfig(BaseModel):
    webhook_url: str = ""  # Discord/Slack-compatible webhook
    on_grab: bool = True
    on_import: bool = True


class AuthConfig(BaseModel):
    api_key: str = ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FATHOM_", env_nested_delimiter="__")

    server: ServerConfig = Field(default_factory=ServerConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    media: MediaConfig = Field(default_factory=MediaConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    tmdb: TMDBConfig = Field(default_factory=TMDBConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)


def _find_config_path() -> Path | None:
    candidates = [
        Path("config.yaml"),
        Path("config.yml"),
        Path(os.environ.get("FATHOM_CONFIG", "config.yaml")),
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


def _load_yaml_overrides(path: Path) -> dict[str, Any]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data if isinstance(data, dict) else {}


def load_settings() -> Settings:
    config_path = _find_config_path()
    if config_path:
        overrides = _load_yaml_overrides(config_path)
        return Settings(**overrides)
    return Settings()


# Module-level singleton — imported by other modules
settings = load_settings()
