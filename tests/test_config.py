from app.config import get_settings


def test_defaults_align_with_env_example(monkeypatch) -> None:
    for key in ("WHISPER_SERVER_BASE_URL", "ENABLE_STARTUP_HEALTH_CHECK"):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()
    try:
        settings = get_settings()
        assert settings.whisper_server_base_url == "http://127.0.0.1:8001"
        assert settings.enable_startup_health_check is False
    finally:
        get_settings.cache_clear()
