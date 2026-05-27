from __future__ import annotations

from unittest.mock import MagicMock, patch

from httpx import RequestError

from app.ai.receipt_extractor import LlamaCppReceiptExtractor


def test_extractor_success_on_first_try():
    extractor = LlamaCppReceiptExtractor("http://localhost", "model")
    with patch("httpx.Client.post") as mock_post:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"status": "success", "summary": {"total": 10000}}'}}]
        }
        mock_post.return_value = mock_response

        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.read_bytes", return_value=b"dummy"
        ):
            result = extractor.extract("dummy.jpg")

        assert result["status"] == "success"
        assert mock_post.call_count == 1


def test_extractor_success_on_retry():
    extractor = LlamaCppReceiptExtractor("http://localhost", "model")
    with patch("httpx.Client.post") as mock_post, patch("time.sleep") as mock_sleep:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": '{"status": "success", "summary": {"total": 10000}}'}}]
        }

        # Fail first 2 times, succeed on 3rd
        mock_post.side_effect = [RequestError("Timeout"), RequestError("Busy"), mock_response]

        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.read_bytes", return_value=b"dummy"
        ):
            result = extractor.extract("dummy.jpg")

        assert result["status"] == "success"
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2


def test_extractor_failed_all_retries():
    extractor = LlamaCppReceiptExtractor("http://localhost", "model")
    with patch("httpx.Client.post") as mock_post, patch("time.sleep") as mock_sleep:
        mock_post.side_effect = RequestError("Server down")

        with patch("pathlib.Path.exists", return_value=True), patch(
            "pathlib.Path.read_bytes", return_value=b"dummy"
        ):
            result = extractor.extract("dummy.jpg")

        assert result["status"] == "failed"
        assert "Failed after 3 attempts" in result["message"]
        assert mock_post.call_count == 3
        assert mock_sleep.call_count == 2
