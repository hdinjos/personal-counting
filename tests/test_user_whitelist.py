from pathlib import Path

from app.bot.handlers import BotHandlers


def _build_handlers(*, enable_user_whitelist: bool, allowed_user_ids: list[int] | None) -> BotHandlers:
    return BotHandlers(
        transaction_service=None,
        report_service=None,
        extractor=None,
        voice_transcriber=None,
        upload_dir=Path("uploads"),
        enable_user_whitelist=enable_user_whitelist,
        allowed_user_ids=allowed_user_ids,
    )


def test_whitelist_disabled_allows_any_user() -> None:
    handlers = _build_handlers(enable_user_whitelist=False, allowed_user_ids=[111])
    assert handlers._is_allowed(111) is True
    assert handlers._is_allowed(222) is True


def test_whitelist_enabled_allows_only_listed_user() -> None:
    handlers = _build_handlers(enable_user_whitelist=True, allowed_user_ids=[111])
    assert handlers._is_allowed(111) is True
    assert handlers._is_allowed(222) is False


def test_whitelist_enabled_with_empty_list_blocks_all_users() -> None:
    handlers = _build_handlers(enable_user_whitelist=True, allowed_user_ids=[])
    assert handlers._is_allowed(111) is False
