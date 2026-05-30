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
    whisper_server_base_url: str
    whisper_server_inference_path: str
    whisper_server_timeout_seconds: int
    whisper_language: str
    ocr_language: str
    database_url: str
    upload_dir: Path
    use_dummy_extractor: bool
    extractor_backend: str
    request_timeout_seconds: int
    timezone: str
    enable_user_whitelist: bool
    allowed_user_ids: list[int]
    enable_startup_health_check: bool


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
        whisper_server_base_url=os.getenv("WHISPER_SERVER_BASE_URL", "http://127.0.0.1:8080").rstrip("/"),
        whisper_server_inference_path=os.getenv("WHISPER_SERVER_INFERENCE_PATH", "/inference"),
        whisper_server_timeout_seconds=int(os.getenv("WHISPER_SERVER_TIMEOUT_SECONDS", "120")),
        whisper_language=os.getenv("WHISPER_LANGUAGE", "id"),
        ocr_language=os.getenv("OCR_LANGUAGE", "id"),
        database_url=os.getenv("DATABASE_URL", "sqlite:///expense-agent.db"),
        upload_dir=upload_dir,
        use_dummy_extractor=_env_bool("USE_DUMMY_EXTRACTOR", False),
        extractor_backend=os.getenv("EXTRACTOR_BACKEND", "llamacpp").lower(),
        request_timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "120")),
        timezone=os.getenv("TZ", "Asia/Jakarta"),
        enable_user_whitelist=_env_bool("ENABLE_USER_WHITELIST", False),
        allowed_user_ids=[int(u.strip()) for u in os.getenv("ALLOWED_USER_IDS", "").split(",") if u.strip().isdigit()],
        enable_startup_health_check=_env_bool("ENABLE_STARTUP_HEALTH_CHECK", True),
    )
