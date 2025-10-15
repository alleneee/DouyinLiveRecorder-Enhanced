"""应用配置。"""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", case_sensitive=False)

    app_name: str = "Douyin Live Recorder"
    version: str = "0.1.0"
    api_prefix: str = "/api"
    database_url: str = "mysql+pymysql://user:password@localhost:3306/douyin"
    sqlalchemy_echo: bool = False


settings = Settings()


__all__ = ["Settings", "settings"]
