from __future__ import annotations

import asyncio

import httpx
import pytest
from PIL import Image

from app.ai.receipt_extractor import LlamaCppReceiptExtractor


class FakeResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, actions) -> None:
        self.actions = list(actions)
        self.calls = []
        self.closed = False

    async def post(self, url, json):
        self.calls.append(json)
        action = self.actions[len(self.calls) - 1]
        if isinstance(action, Exception):
            raise action
        return FakeResponse(action)

    async def aclose(self) -> None:
        self.closed = True


def _model_response(content):
    return {"choices": [{"message": {"content": content}}]}


def _extractor(monkeypatch, fake: FakeClient) -> LlamaCppReceiptExtractor:
    ex = LlamaCppReceiptExtractor(base_url="http://llama:8000/v1", model="m")
    monkeypatch.setattr(ex, "_get_client", lambda: fake)
    return ex


@pytest.mark.asyncio
async def test_extract_ocr_success(monkeypatch) -> None:
    fake = FakeClient([_model_response('{"status":"success","summary":{"total":50000}}')])
    ex = _extractor(monkeypatch, fake)

    result = await ex.extract(ocr_text="Toko ABC\nTotal 50000")

    assert result["status"] == "success"
    assert "messages" in fake.calls[0]


@pytest.mark.asyncio
async def test_extract_text_payload_includes_transcription(monkeypatch) -> None:
    fake = FakeClient([_model_response('{"status":"success"}')])
    ex = _extractor(monkeypatch, fake)

    result = await ex.extract(text_input="beli kopi 20000")

    assert result["status"] == "success"
    user_content = fake.calls[0]["messages"][-1]["content"]
    assert "beli kopi 20000" in user_content


@pytest.mark.asyncio
async def test_extract_vision_payload_is_multimodal(monkeypatch, tmp_path) -> None:
    image_path = tmp_path / "receipt.jpg"
    Image.new("RGB", (4, 4), "white").save(image_path)

    fake = FakeClient([_model_response('{"status":"success"}')])
    ex = _extractor(monkeypatch, fake)

    result = await ex.extract(image_path=str(image_path))

    assert result["status"] == "success"
    content = fake.calls[0]["messages"][-1]["content"]
    assert isinstance(content, list)
    assert any(part.get("type") == "image_url" for part in content)


@pytest.mark.asyncio
async def test_retry_then_success(monkeypatch) -> None:
    async def _no_sleep(_seconds):
        return None

    monkeypatch.setattr(asyncio, "sleep", _no_sleep)
    fake = FakeClient([httpx.ConnectError("down"), _model_response('{"status":"success"}')])
    ex = _extractor(monkeypatch, fake)

    result = await ex.extract(text_input="x")

    assert result["status"] == "success"
    assert len(fake.calls) == 2


@pytest.mark.asyncio
async def test_invalid_json_returns_failed_payload(monkeypatch) -> None:
    fake = FakeClient([_model_response("bukan json sama sekali")])
    ex = _extractor(monkeypatch, fake)

    result = await ex.extract(ocr_text="x")

    assert result["status"] == "failed"
    assert result["message"] == "Invalid JSON response from model"


@pytest.mark.asyncio
async def test_content_as_list_is_parsed(monkeypatch) -> None:
    fake = FakeClient([_model_response([{"text": '{"status":"success"}'}])])
    ex = _extractor(monkeypatch, fake)

    result = await ex.extract(ocr_text="x")

    assert result["status"] == "success"


@pytest.mark.asyncio
async def test_aclose_closes_client() -> None:
    ex = LlamaCppReceiptExtractor(base_url="http://llama:8000/v1", model="m")
    fake = FakeClient([])
    ex._client = fake

    await ex.aclose()

    assert fake.closed is True
    assert ex._client is None
