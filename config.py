from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()


def _split_csv(value: str, default: Optional[List[str]] = None) -> List[str]:
    if not value:
        return default or []
    return [item.strip() for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Settings:
    secret_key: str
    app_env: str
    proxy_api_url: str
    proxy_primary_token: str
    proxy_fallback_token: Optional[str]
    proxy_timeout: int
    allowed_origins: List[str]
    rate_limit_per_minute: int
    rate_limit_per_hour: int
    app_name: str
    app_version: str

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            secret_key=os.getenv("SECRET_KEY", "change_me"),
            app_env=os.getenv("APP_ENV", "development"),
            proxy_api_url=os.getenv("PROXY_API_URL", "http://85.114.224.45:8000"),
            proxy_primary_token=_require_env("PROXY_PRIMARY_TOKEN"),
            proxy_fallback_token=os.getenv("PROXY_FALLBACK_TOKEN"),
            proxy_timeout=int(os.getenv("PROXY_TIMEOUT", "5")),
            allowed_origins=_split_csv(os.getenv("ALLOWED_ORIGINS", "*"), default=["*"]),
            rate_limit_per_minute=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")),
            rate_limit_per_hour=int(os.getenv("RATE_LIMIT_PER_HOUR", "1000")),
            app_name=os.getenv("APP_NAME", "Firebird DB Proxy"),
            app_version=os.getenv("APP_VERSION", "1.0.0"),
        )


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Environment variable '{name}' is required but was not provided.")
    return value


settings = Settings.from_env()

