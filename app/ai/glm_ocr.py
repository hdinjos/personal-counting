from __future__ import annotations

import base64
import logging
import time
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_MIME_MAP = {".png": "image/png", ".webp": "image/webp"}


class LlamaCppOCREngine:
    """OCR engine yang memanggil GLM-OCR GGUF via llama-server (OpenAI-compatible vision API)."""

    def __init__(
        self,
        base_url: str,
        model: str,
        prompt: str,
        timeout_seconds: int = 120,
        max_tokens: int = 4096,
        max_retries: int = 2,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.prompt = prompt
        self.timeout_seconds = timeout_seconds
        self.max_tokens = max_tokens
        self.max_retries = max_retries

    def extract_text(self, image_path: str) -> str:
        path = Path(image_path)
        if not path.exists():
            logger.warning("GLM-OCR: file not found: %s", image_path)
            return ""

        mime = _MIME_MAP.get(path.suffix.lower(), "image/jpeg")
        data_uri = f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": data_uri}},
                        {"type": "text", "text": self.prompt},
                    ],
                }
            ],
            "temperature": 0.1,
            "top_k": 1,
            "max_tokens": self.max_tokens,
        }

        url = f"{self.base_url}/chat/completions"
        last_exc: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    response = client.post(url, json=payload)
                    response.raise_for_status()
                    data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if isinstance(content, str):
                    return content.strip()
                return ""
            except (httpx.TimeoutException, httpx.ConnectError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    time.sleep(2**attempt)
            except Exception as exc:  # noqa: BLE001
                logger.warning("GLM-OCR request failed: %s", exc)
                return ""

        logger.warning("GLM-OCR request failed after retries: %s", last_exc)
        return ""
