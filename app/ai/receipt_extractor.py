from __future__ import annotations

import base64
import io
import mimetypes
from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from app.ai.prompts import RECEIPT_EXTRACTION_PROMPT
from app.utils.json_utils import extract_json_from_text


def _failed_payload(message: str = "Extractor error") -> dict[str, Any]:
    return {
        "status": "failed",
        "message": message,
        "store": {"name": None, "address": None, "phone": None},
        "transaction": {
            "date": None,
            "time": None,
            "invoice_number": None,
            "payment_method": None,
        },
        "items": [],
        "summary": {
            "subtotal": None,
            "discount": None,
            "tax": None,
            "service_charge": None,
            "total": None,
            "paid": None,
            "change": None,
        },
        "raw_text": None,
    }


class BaseReceiptExtractor(ABC):
    @abstractmethod
    async def extract(self, image_path: str) -> dict[str, Any]:
        raise NotImplementedError


class DummyReceiptExtractor(BaseReceiptExtractor):
    async def extract(self, image_path: str) -> dict[str, Any]:
        _ = image_path
        return {
            "status": "success",
            "message": None,
            "store": {"name": "Dummy Store", "address": None, "phone": None},
            "transaction": {
                "date": date.today().strftime("%Y-%m-%d"),
                "time": "10:00",
                "invoice_number": "DUMMY-001",
                "payment_method": "cash",
            },
            "items": [
                {
                    "name": "Beras 5kg",
                    "category": "sembako",
                    "quantity": 1,
                    "unit": "pcs",
                    "unit_price": 60000,
                    "subtotal": 60000,
                }
            ],
            "summary": {
                "subtotal": 60000,
                "discount": 0,
                "tax": 0,
                "service_charge": 0,
                "total": 60000,
                "paid": 100000,
                "change": 40000,
            },
            "raw_text": "dummy extractor",
        }


class LlamaCppReceiptExtractor(BaseReceiptExtractor):
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 120) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    async def extract(self, image_path: str) -> dict[str, Any]:
        image_file = Path(image_path)
        if not image_file.exists():
            return _failed_payload("Image file not found")

        try:
            data_url = self._build_data_url(image_file)
            payload = self._build_payload(data_url)

            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(f"{self.base_url}/chat/completions", json=payload)
                response.raise_for_status()
                raw = response.json()
        except Exception as exc:  # noqa: BLE001
            return _failed_payload(str(exc))

        content = self._extract_content(raw)
        parsed = extract_json_from_text(content)
        if not parsed:
            return _failed_payload("Invalid JSON response from model")
        if "status" not in parsed:
            parsed["status"] = "failed"
        return parsed

    def _build_payload(self, data_url: str) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Kamu adalah AI ekstraktor struk belanja."},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": RECEIPT_EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

    @staticmethod
    def _extract_content(raw_response: dict[str, Any]) -> str:
        choices = raw_response.get("choices", [])
        if not choices:
            return ""

        content = choices[0].get("message", {}).get("content", "")
        if isinstance(content, str):
            return content

        if isinstance(content, list):
            texts: list[str] = []
            for part in content:
                if isinstance(part, dict):
                    text = part.get("text")
                    if isinstance(text, str):
                        texts.append(text)
            return "\n".join(texts)

        return ""

    @staticmethod
    def _build_data_url(image_file: Path) -> str:
        mime, _ = mimetypes.guess_type(str(image_file))
        mime = mime or "image/jpeg"
        
        # Resize image if it's too large
        with Image.open(image_file) as img:
            max_size = 1280
            if max(img.width, img.height) > max_size:
                img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                buffer = io.BytesIO()
                # Determine format based on mime or default to JPEG
                fmt = "PNG" if mime == "image/png" else "JPEG"
                if img.mode != "RGB" and fmt == "JPEG":
                    img = img.convert("RGB")
                img.save(buffer, format=fmt, quality=85)
                image_bytes = buffer.getvalue()
            else:
                image_bytes = image_file.read_bytes()

        encoded = base64.b64encode(image_bytes).decode("ascii")
        return f"data:{mime};base64,{encoded}"

