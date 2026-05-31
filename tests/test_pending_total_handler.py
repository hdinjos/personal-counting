from __future__ import annotations

from datetime import datetime

import pytest

from app.bot.handlers import PENDING_TOTAL_KEY, PENDING_TOTAL_TIMEOUT_SECONDS, BotHandlers


class DummyTransactionService:
    def __init__(self, result: dict | None = None) -> None:
        self.result = result or {
            "status": "success",
            "store_name": "Warung",
            "date": "2026-05-27",
            "total": 12000,
            "manual_total_input": True,
        }
        self.calls: list[tuple] = []

    def expected_total(self, normalized):
        # Default: consistent total so the save path proceeds to storage.
        return None, normalized

    def store_confirmed_transaction(self, *args):
        self.calls.append(args)
        return self.result


class DummyUser:
    def __init__(self, user_id: int = 1, username: str = "user") -> None:
        self.id = user_id
        self.username = username


class DummyMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text: str, **kwargs):
        self.replies.append(text)
        return None


class DummyUpdate:
    def __init__(self, text: str = "") -> None:
        self.message = DummyMessage(text=text)
        self.effective_user = DummyUser()


class DummyContext:
    def __init__(self) -> None:
        self.user_data: dict = {}


def _build_handlers(service: DummyTransactionService) -> BotHandlers:
    return BotHandlers(
        transaction_service=service,
        report_service=None,
        extractor=None,
        voice_transcriber=None,
        upload_dir=None,
    )


def _pending_payload(created_at_ts: float) -> dict:
    return {
        "telegram_file_id": "uploads/1.ogg",
        "normalized_payload": {
            "status": "success",
            "store": {"name": "Warung"},
            "transaction": {"date": "2026-05-27"},
            "items": [{"name": "Kopi", "subtotal": 12000, "quantity": 1}],
            "summary": {"total": 15000},
        },
        "upload_date": "2026-05-27",
        "created_at_ts": created_at_ts,
    }


@pytest.mark.asyncio
async def test_handle_pending_total_text_success() -> None:
    service = DummyTransactionService()
    handlers = _build_handlers(service)
    update = DummyUpdate(text="12000")
    context = DummyContext()
    context.user_data[PENDING_TOTAL_KEY] = _pending_payload(datetime.now().timestamp())

    await handlers.handle_pending_total_text(update, context)

    assert len(service.calls) == 1
    assert PENDING_TOTAL_KEY not in context.user_data
    assert any("Transaksi berhasil disimpan" in reply for reply in update.message.replies)


@pytest.mark.asyncio
async def test_handle_pending_total_text_invalid_amount_keeps_pending() -> None:
    service = DummyTransactionService()
    handlers = _build_handlers(service)
    update = DummyUpdate(text="seribu")
    context = DummyContext()
    context.user_data[PENDING_TOTAL_KEY] = _pending_payload(datetime.now().timestamp())

    await handlers.handle_pending_total_text(update, context)

    assert len(service.calls) == 0
    assert PENDING_TOTAL_KEY in context.user_data
    assert any("Nominal tidak valid" in reply for reply in update.message.replies)


@pytest.mark.asyncio
async def test_handle_pending_total_text_cancel() -> None:
    service = DummyTransactionService()
    handlers = _build_handlers(service)
    update = DummyUpdate(text="batal")
    context = DummyContext()
    context.user_data[PENDING_TOTAL_KEY] = _pending_payload(datetime.now().timestamp())

    await handlers.handle_pending_total_text(update, context)

    assert len(service.calls) == 0
    assert PENDING_TOTAL_KEY not in context.user_data
    assert any("dibatalkan" in reply for reply in update.message.replies)


@pytest.mark.asyncio
async def test_handle_pending_total_text_expired() -> None:
    service = DummyTransactionService()
    handlers = _build_handlers(service)
    update = DummyUpdate(text="12000")
    context = DummyContext()
    context.user_data[PENDING_TOTAL_KEY] = _pending_payload(
        datetime.now().timestamp() - PENDING_TOTAL_TIMEOUT_SECONDS - 1
    )

    await handlers.handle_pending_total_text(update, context)

    assert len(service.calls) == 0
    assert PENDING_TOTAL_KEY not in context.user_data
    assert any("kedaluwarsa" in reply for reply in update.message.replies)


@pytest.mark.asyncio
async def test_batal_pending_total_without_pending() -> None:
    service = DummyTransactionService()
    handlers = _build_handlers(service)
    update = DummyUpdate(text="/batal")
    context = DummyContext()

    await handlers.batal_pending_total(update, context)

    assert any("Tidak ada transaksi" in reply for reply in update.message.replies)


@pytest.mark.asyncio
async def test_batal_pending_total_with_pending() -> None:
    service = DummyTransactionService()
    handlers = _build_handlers(service)
    update = DummyUpdate(text="/batal")
    context = DummyContext()
    context.user_data[PENDING_TOTAL_KEY] = _pending_payload(datetime.now().timestamp())

    await handlers.batal_pending_total(update, context)

    assert PENDING_TOTAL_KEY not in context.user_data
    assert any("dibatalkan" in reply for reply in update.message.replies)


def _save_pending(created_at_ts: float) -> dict:
    pending = _pending_payload(created_at_ts)
    pending["type"] = "save_transaction"
    return pending


@pytest.mark.asyncio
async def test_save_transaction_confirm_stores() -> None:
    service = DummyTransactionService()
    handlers = _build_handlers(service)
    update = DummyUpdate(text="ya")
    context = DummyContext()
    context.user_data[PENDING_TOTAL_KEY] = _save_pending(datetime.now().timestamp())

    await handlers.handle_pending_total_text(update, context)

    assert len(service.calls) == 1
    assert PENDING_TOTAL_KEY not in context.user_data
    assert any("berhasil disimpan" in reply for reply in update.message.replies)


@pytest.mark.asyncio
async def test_save_transaction_mismatch_switches_to_manual_total() -> None:
    service = DummyTransactionService()
    # Report an inconsistent expected total.
    service.expected_total = lambda normalized: (99999, normalized)
    handlers = _build_handlers(service)
    update = DummyUpdate(text="ya")
    context = DummyContext()
    context.user_data[PENDING_TOTAL_KEY] = _save_pending(datetime.now().timestamp())

    await handlers.handle_pending_total_text(update, context)

    assert len(service.calls) == 0
    assert context.user_data[PENDING_TOTAL_KEY]["type"] == "manual_total"
    assert any("tidak konsisten" in reply for reply in update.message.replies)

