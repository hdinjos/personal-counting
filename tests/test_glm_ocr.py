import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.ai.glm_ocr import LlamaCppOCREngine


@pytest.fixture
def engine():
    return LlamaCppOCREngine(
        base_url="http://127.0.0.1:8002/v1",
        model="glm-ocr",
        prompt="OCR markdown.",
    )


@pytest.fixture
def fake_image(tmp_path):
    p = tmp_path / "receipt.jpg"
    p.write_bytes(b"\xff\xd8\xff\xe0fake-jpeg-data")
    return p


def _mock_response(content: str):
    resp = MagicMock()
    resp.status_code = 200
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


def test_default_ocr_backend_is_paddleocr():
    import os
    from unittest.mock import patch as env_patch

    env = {k: v for k, v in os.environ.items() if not k.startswith("OCR_BACKEND")}
    with env_patch.dict(os.environ, env, clear=True):
        from app.config import get_settings
        get_settings.cache_clear()
        os.environ.pop("OCR_BACKEND", None)
        get_settings.cache_clear()
        s = get_settings()
        assert s.ocr_backend == "paddleocr"
        get_settings.cache_clear()


def test_llamacpp_ocr_builds_correct_payload(engine, fake_image):
    captured = {}

    def mock_post(url, json=None, **kwargs):
        captured["url"] = url
        captured["payload"] = json
        return _mock_response("OCR result")

    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        engine.extract_text(str(fake_image))

    assert captured["url"] == "http://127.0.0.1:8002/v1/chat/completions"
    payload = captured["payload"]
    assert payload["model"] == "glm-ocr"
    assert payload["temperature"] == 0.1
    assert payload["top_k"] == 1
    assert payload["max_tokens"] == 4096
    msg_content = payload["messages"][0]["content"]
    assert msg_content[0]["type"] == "image_url"
    assert msg_content[0]["image_url"]["url"].startswith("data:image/jpeg;base64,")
    assert msg_content[1]["type"] == "text"
    assert msg_content[1]["text"] == "OCR markdown."


def test_llamacpp_ocr_success_returns_text(engine, fake_image):
    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.post.return_value = _mock_response("  Toko ABC\nItem 1  10000  ")
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        result = engine.extract_text(str(fake_image))

    assert result == "Toko ABC\nItem 1  10000"


def test_llamacpp_ocr_http_error_returns_empty(engine, fake_image):
    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        resp = MagicMock()
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=MagicMock()
        )
        mock_client.post.return_value = resp
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        result = engine.extract_text(str(fake_image))

    assert result == ""


def test_llamacpp_ocr_timeout_returns_empty(fake_image):
    engine = LlamaCppOCREngine(
        base_url="http://127.0.0.1:8002/v1",
        model="glm-ocr",
        prompt="OCR markdown.",
        max_retries=0,
    )
    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        result = engine.extract_text(str(fake_image))

    assert result == ""


def test_llamacpp_ocr_invalid_json_returns_empty(engine, fake_image):
    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.json.return_value = {"unexpected": "format"}
        mock_client.post.return_value = resp
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        result = engine.extract_text(str(fake_image))

    assert result == ""


def test_llamacpp_ocr_file_not_found_returns_empty(engine):
    result = engine.extract_text("/nonexistent/path/image.jpg")
    assert result == ""


def test_llamacpp_ocr_png_mime(engine, tmp_path):
    p = tmp_path / "receipt.png"
    p.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    captured = {}

    def mock_post(url, json=None, **kwargs):
        captured["payload"] = json
        return _mock_response("png result")

    with patch("httpx.Client") as MockClient:
        mock_client = MagicMock()
        mock_client.post = mock_post
        mock_client.__enter__ = lambda s: mock_client
        mock_client.__exit__ = MagicMock(return_value=False)
        MockClient.return_value = mock_client

        engine.extract_text(str(p))

    data_uri = captured["payload"]["messages"][0]["content"][0]["image_url"]["url"]
    assert data_uri.startswith("data:image/png;base64,")
