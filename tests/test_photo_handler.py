from __future__ import annotations

from pathlib import Path

import pytest

from app.bot.handlers import PENDING_TOTAL_KEY, BotHandlers
from app.services.transaction_service import TransactionService


SUCCESS_PAYLOAD = {
    "status": "success",
    "store": {"name": "Toko"},
    "transaction": {"date": "2026-05-27", "time": "10:00"},
    "items": [{"name": "Kopi", "unit_price": 12000, "quantity": 1, "subtotal": 12000}],
    "summary": {"total": 12000},
}


class FakeRepository:
    def create_transaction(self, **kwargs):
        raise AssertionError("storage should not happen during confirmation step")


class DummyExtractor:
    def __init__(self, payload) -> None:
        self.payload = payload
        self.calls: list[dict] = []

    async def extract(self, ocr_text=None, text_input=None, image_path=None):
        self.calls.append({"ocr_text": ocr_text, "text_input": text_input, "image_path": image_path})
        return self.payload


class DummyOCR:
    def __init__(self, text: str) -> None:
        self.text = text

    def extract_text(self, path: str) -> str:
        return self.text


class DummyTelegramFile:
    async def download_to_drive(self, custom_path):
        Path(custom_path).write_bytes(b"data")


class DummyBot:
    async def get_file(self, file_id):
        return DummyTelegramFile()


class DummyBotMessage:
    def __init__(self) -> None:
        self.texts: list[str] = []

    async def edit_text(self, text):
        self.texts.append(text)

    async def delete(self):
        return None


class DummyMessage:
    def __init__(self, photo=None, voice=None, text="") -> None:
        self.photo = photo or []
        self.voice = voice
        self.document = None
        self.text = text
        self.replies: list[str] = []

    async def reply_text(self, text, **kwargs):
        self.replies.append(text)
        return DummyBotMessage()


class DummyUser:
    id = 1
    username = "user"


class DummyUpdate:
    def __init__(self, message) -> None:
        self.message = message
        self.effective_user = DummyUser()


class DummyContext:
    def __init__(self) -> None:
        self.user_data: dict = {}
        self.bot = DummyBot()


class DummyPhoto:
    file_id = "PHOTO_FID"


def _handlers(extractor, ocr_engine, upload_dir) -> BotHandlers:
    return BotHandlers(
        transaction_service=TransactionService(FakeRepository()),
        report_service=None,
        extractor=extractor,
        voice_transcriber=None,
        upload_dir=upload_dir,
        ocr_engine=ocr_engine,
    )


@pytest.mark.asyncio
async def test_handle_photo_ocr_path_sets_pending(tmp_path) -> None:
    extractor = DummyExtractor(SUCCESS_PAYLOAD)
    handlers = _handlers(extractor, DummyOCR("Toko\nKopi 12000"), tmp_path)
    update = DummyUpdate(DummyMessage(photo=[DummyPhoto()]))
    context = DummyContext()

    await handlers.handle_photo(update, context)

    assert extractor.calls[0]["ocr_text"] == "Toko\nKopi 12000"
    pending = context.user_data[PENDING_TOTAL_KEY]
    assert pending["type"] == "save_transaction"
    assert pending["telegram_file_id"] == "PHOTO_FID"
    assert any("terbaca" in r for r in update.message.replies)
    # Temp file cleaned up.
    assert list(tmp_path.glob("1_*")) == []


@pytest.mark.asyncio
async def test_handle_photo_vlm_path_uses_image(tmp_path) -> None:
    extractor = DummyExtractor(SUCCESS_PAYLOAD)
    handlers = _handlers(extractor, None, tmp_path)  # ocr_engine=None -> VLM
    update = DummyUpdate(DummyMessage(photo=[DummyPhoto()]))
    context = DummyContext()

    await handlers.handle_photo(update, context)

    assert extractor.calls[0]["image_path"] is not None
    assert extractor.calls[0]["ocr_text"] is None
    assert PENDING_TOTAL_KEY in context.user_data


@pytest.mark.asyncio
async def test_handle_photo_failed_extraction_no_pending(tmp_path) -> None:
    extractor = DummyExtractor({"status": "failed", "summary": {}, "items": []})
    handlers = _handlers(extractor, DummyOCR("noise"), tmp_path)
    update = DummyUpdate(DummyMessage(photo=[DummyPhoto()]))
    context = DummyContext()

    await handlers.handle_photo(update, context)

    assert PENDING_TOTAL_KEY not in context.user_data


class DummyVoice:
    file_id = "VOICE_FID"


class DummyTranscriber:
    def __init__(self, text: str) -> None:
        self.text = text

    async def transcribe(self, path: str) -> str:
        return self.text


def _voice_handlers(extractor, transcriber, upload_dir) -> BotHandlers:
    return BotHandlers(
        transaction_service=TransactionService(FakeRepository()),
        report_service=None,
        extractor=extractor,
        voice_transcriber=transcriber,
        upload_dir=upload_dir,
    )


@pytest.mark.asyncio
async def test_handle_voice_sets_pending(tmp_path) -> None:
    extractor = DummyExtractor(SUCCESS_PAYLOAD)
    handlers = _voice_handlers(extractor, DummyTranscriber("beli kopi 12000"), tmp_path)
    update = DummyUpdate(DummyMessage(voice=DummyVoice()))
    context = DummyContext()

    await handlers.handle_voice(update, context)

    assert extractor.calls[0]["text_input"] == "beli kopi 12000"
    pending = context.user_data[PENDING_TOTAL_KEY]
    assert pending["type"] == "save_transaction"
    assert pending["telegram_file_id"] == "VOICE_FID"


@pytest.mark.asyncio
async def test_handle_voice_empty_transcription_no_pending(tmp_path) -> None:
    extractor = DummyExtractor(SUCCESS_PAYLOAD)
    handlers = _voice_handlers(extractor, DummyTranscriber(""), tmp_path)
    update = DummyUpdate(DummyMessage(voice=DummyVoice()))
    context = DummyContext()

    await handlers.handle_voice(update, context)

    assert PENDING_TOTAL_KEY not in context.user_data
    assert extractor.calls == []
