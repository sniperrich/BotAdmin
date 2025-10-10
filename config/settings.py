"""Application configuration helpers."""
from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    db_path: Path
    static_dir: Path
    secret_key: str

    @property
    def db_path_str(self) -> str:
        return str(self.db_path)

    @property
    def static_dir_str(self) -> str:
        return str(self.static_dir)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    base_dir = BASE_DIR
    db_path = Path(os.environ.get("BOT_ADMIN_DB") or (base_dir / "bot_admin.db"))
    static_dir = Path(os.environ.get("STATIC_ROOT") or (base_dir / "static"))
    secret_key = os.environ.get("APP_SECRET", "dev-secret")
    return Settings(base_dir=base_dir, db_path=db_path, static_dir=static_dir, secret_key=secret_key)


__all__ = ["Settings", "get_settings", "BASE_DIR"]
