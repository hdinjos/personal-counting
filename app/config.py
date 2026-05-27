from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    llamacpp_base_url: str
    llamacpp_model: str
    database_url: str
    upload_dir: Path
    use_dummy_extractor: bool
    extractor_backend: str
    request_timeout_seconds: int
    timezone: str
    allowed_user_ids: list[int]


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    upload_dir = Path(os.getenv("UPLOAD_DIR", "uploads"))
    if not upload_dir.is_absolute():
        upload_dir = PROJECT_ROOT / upload_dir

    return Settings(
        telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
        llamacpp_base_url=os.getenv("LLAMACPP_BASE_URL", "http://localhost:8000/v1").rstrip("/"),
        llamacpp_model=os.getenv("LLAMACPP_MODEL", "local-qwen3-vl"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///expense-agent.db"),
        upload_dir=upload_dir,
        use_dummy_extractor=_env_bool("USE_DUMMY_EXTRACTOR", False),
        extractor_backend=os.getenv("EXTRACTOR_BACKEND", "llamacpp").lower(),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120")),
        timezone=os.getenv("TZ", "Asia/Jakarta"),
        allowed_user_ids=[int(u.strip()) for u in os.getenv("ALLOWED_USER_IDS", "").split(",") if u.strip().isdigit()],
    )

