from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Optional

import httpx

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
    async def extract(self, ocr_text: Optional[str] = None, text_input: Optional[str] = None) -> dict[str, Any]:
        raise NotImplementedError


class DummyReceiptExtractor(BaseReceiptExtractor):
    async def extract(self, ocr_text: Optional[str] = None, text_input: Optional[str] = None) -> dict[str, Any]:
        _ = ocr_text
        _ = text_input
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
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 120, max_retries: int = 2) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def extract(self, ocr_text: Optional[str] = None, text_input: Optional[str] = None) -> dict[str, Any]:
        if not ocr_text and not text_input:
            return _failed_payload("ocr_text atau text_input harus diisi")

        try:
            payload = self._build_ocr_payload(ocr_text) if ocr_text else self._build_text_payload(text_input)
            raw = await self._request_with_retry(payload)
        except Exception as exc:  # noqa: BLE001
            return _failed_payload(str(exc))

        content = self._extract_content(raw)
        parsed = extract_json_from_text(content)
        if not parsed:
            return _failed_payload("Invalid JSON response from model")
        if "status" not in parsed:
            parsed["status"] = "failed"
        return parsed

    async def _request_with_retry(self, payload: dict[str, Any]) -> dict[str, Any]:
        import asyncio

        last_exc: Exception | None = None
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(f"{self.base_url}/chat/completions", json=payload)
                    response.raise_for_status()
                    return response.json()
            except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
        raise last_exc

    def _build_text_payload(self, text_input: str) -> dict[str, Any]:
        extra_instruction = (
            "\n\nATURAN TAMBAHAN untuk input teks/suara:\n"
            "- Jika pengguna TIDAK menyebutkan tanggal, isi transaction.date dengan null.\n"
            "- Jika pengguna TIDAK menyebutkan waktu/jam, isi transaction.time dengan null.\n"
            "- JANGAN mengarang tanggal atau waktu yang tidak disebutkan pengguna.\n"
            "- Jika pengguna menyebut voucher/diskon/potongan, masukkan total pengurangannya ke summary.discount sebagai angka positif."
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Kamu adalah AI asisten pencatat pengeluaran. Ekstrak data transaksi dari pesan suara/teks yang diberikan pengguna."},
                {
                    "role": "user",
                    "content": f"{RECEIPT_EXTRACTION_PROMPT}{extra_instruction}\n\nBerikut adalah hasil transkripsi pesan pengguna:\n\n{text_input}",
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

    def _build_ocr_payload(self, ocr_text: str) -> dict[str, Any]:
        print(ocr_text)
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Kamu adalah AI ekstraktor struk belanja dari teks hasil OCR."},
                {
                    "role": "user",
                    "content": f"{RECEIPT_EXTRACTION_PROMPT}\n\nBerikut teks hasil OCR dari struk:\n\n{ocr_text}",
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
