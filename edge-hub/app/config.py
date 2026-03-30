from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    base = Path(os.environ.get("GDT_HUB_DATA", "")).expanduser()
    if base and base.is_absolute():
        return base
    return Path(__file__).resolve().parent.parent / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GDT_", extra="ignore")

    host: str = "127.0.0.1"
    port: int = 8756
    database_url: str = ""  # set from data_dir if empty

    @property
    def data_dir(self) -> Path:
        d = _default_data_dir()
        d.mkdir(parents=True, exist_ok=True)
        return d

    def sqlalchemy_url(self) -> str:
        if self.database_url:
            return self.database_url
        return f"sqlite:///{self.data_dir / 'hub.db'}"


settings = Settings()
