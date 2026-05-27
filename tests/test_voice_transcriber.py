from __future__ import annotations

import httpx
import pytest

from app.ai.voice_transcriber import VoiceTranscriber


class DummyAsyncClient:
    def __init__(self, response: httpx.Response | None = None, post_error: Exception | None = None) -> None:
        self.response = response
        self.post_error = post_error
        self.timeout = None
        self.last_url: str | None = None
        self.last_files = None

    async def __aenter__(self) -> "DummyAsyncClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, files):
        self.last_url = url
        self.last_files = files
        if self.post_error is not None:
            raise self.post_error
        if self.response is None:
            raise AssertionError("Dummy response must be provided")
        return self.response


def _patch_async_client(monkeypatch: pytest.MonkeyPatch, client: DummyAsyncClient) -> None:
    def factory(*args, **kwargs):
        client.timeout = kwargs.get("timeout")
        return client

    monkeypatch.setattr("app.ai.voice_transcriber.httpx.AsyncClient", factory)


def _response(status_code: int, body: str) -> httpx.Response:
    request = httpx.Request("POST", "http://127.0.0.1:8080/inference")
    return httpx.Response(
        status_code,
        request=request,
        content=body.encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )


@pytest.mark.asyncio
async def test_transcribe_success(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"dummy-ogg")

    client = DummyAsyncClient(response=_response(200, '{"text":"  beli kopi  "}'))
    _patch_async_client(monkeypatch, client)

    transcriber = VoiceTranscriber(
        base_url="http://127.0.0.1:8080",
        inference_path="/inference",
        timeout_seconds=30,
        language="id",
    )

    text = await transcriber.transcribe(str(audio_path))

    assert text == "beli kopi"
    assert client.last_url == "http://127.0.0.1:8080/inference"
    fields = {key: value for key, value in client.last_files}
    assert fields["language"] == (None, "id")
    assert fields["response_format"] == (None, "json")


@pytest.mark.asyncio
async def test_transcribe_returns_empty_when_text_missing(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"dummy-ogg")

    client = DummyAsyncClient(response=_response(200, "{}"))
    _patch_async_client(monkeypatch, client)

    transcriber = VoiceTranscriber(base_url="http://127.0.0.1:8080")
    text = await transcriber.transcribe(str(audio_path))

    assert text == ""


@pytest.mark.asyncio
async def test_transcribe_raises_on_invalid_json(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"dummy-ogg")

    client = DummyAsyncClient(response=_response(200, "not-json"))
    _patch_async_client(monkeypatch, client)

    transcriber = VoiceTranscriber(base_url="http://127.0.0.1:8080")

    with pytest.raises(RuntimeError, match="Invalid JSON response from whisper-server"):
        await transcriber.transcribe(str(audio_path))


@pytest.mark.asyncio
async def test_transcribe_raises_on_http_failure(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"dummy-ogg")

    request = httpx.Request("POST", "http://127.0.0.1:8080/inference")
    connect_error = httpx.ConnectError("connection failed", request=request)
    client = DummyAsyncClient(post_error=connect_error)
    _patch_async_client(monkeypatch, client)

    transcriber = VoiceTranscriber(base_url="http://127.0.0.1:8080")

    with pytest.raises(RuntimeError, match="whisper-server request failed"):
        await transcriber.transcribe(str(audio_path))


@pytest.mark.asyncio
async def test_transcribe_raises_with_convert_hint_for_ogg_bad_request(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    audio_path = tmp_path / "voice.ogg"
    audio_path.write_bytes(b"dummy-ogg")

    client = DummyAsyncClient(response=_response(400, "Invalid request"))
    _patch_async_client(monkeypatch, client)

    transcriber = VoiceTranscriber(base_url="http://127.0.0.1:8080")

    with pytest.raises(RuntimeError, match="--convert"):
        await transcriber.transcribe(str(audio_path))
