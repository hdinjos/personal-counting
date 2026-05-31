from __future__ import annotations

import base64
import os
from abc import ABC, abstractmethod
from datetime import date
from typing import Any, Optional

import httpx

from app.ai.ocr import preprocess_for_vlm
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
    async def extract(self, ocr_text: Optional[str] = None, text_input: Optional[str] = None, image_path: Optional[str] = None) -> dict[str, Any]:
        raise NotImplementedError


class DummyReceiptExtractor(BaseReceiptExtractor):
    async def extract(self, ocr_text: Optional[str] = None, text_input: Optional[str] = None, image_path: Optional[str] = None) -> dict[str, Any]:
        _ = ocr_text
        _ = text_input
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
    def __init__(self, base_url: str, model: str, timeout_seconds: int = 120, max_retries: int = 2) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries

    async def extract(self, ocr_text: Optional[str] = None, text_input: Optional[str] = None, image_path: Optional[str] = None) -> dict[str, Any]:
        if not ocr_text and not text_input and not image_path:
            return _failed_payload("ocr_text, text_input, atau image_path harus diisi")

        try:
            if image_path:
                payload = self._build_vision_payload(image_path)
            elif ocr_text:
                payload = self._build_ocr_payload(ocr_text)
            else:
                payload = self._build_text_payload(text_input)
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
        ocr_instruction = (
            "\n\nATURAN TAMBAHAN untuk teks hasil OCR:\n"
            "- Teks berasal dari OCR struk, urutannya sudah diatur per baris (kiri→kanan, atas→bawah).\n"
            "- Mungkin ada salah baca karakter (mis. O↔0, l/I↔1, S↔5, 'lotal'→'Total', 'Me1'→'Mei'). Perbaiki bila konteksnya jelas, TAPI jangan mengarang data.\n"
            "- Abaikan karakter tunggal atau pendek acak (1-2 huruf/angka seperti 'G', 'T', 'F4', 'H3') yang muncul di pinggir baris — ini noise dari latar belakang foto, BUKAN bagian dari struk.\n"
            "- Dalam satu baris, nama item biasanya di kiri dan harga/qty di kanan; pasangkan item dengan harga/subtotal pada baris yang sama.\n"
            "- Pada struk minimarket, setiap baris item sering menampilkan harga DUA KALI: angka tanpa separator ribuan (mis. 13700) lalu angka dengan koma (mis. 13,700). Keduanya adalah NILAI YANG SAMA. Gunakan angka paling kanan sebagai subtotal.\n"
            "- Angka nominal PALING KANAN pada baris item adalah SUBTOTAL baris (sudah termasuk kuantitas) → isikan ke item.subtotal; JANGAN mengalikannya lagi dengan quantity.\n"
            "- Anggap sebuah angka sebagai unit_price HANYA bila muncul dalam pola 'qty x harga', 'qty × harga', atau '@harga'. Jika tidak ada pola itu, hitung unit_price = subtotal / quantity.\n"
            "- Baris 'VOUCHER', 'DISKON', atau angka dalam tanda kurung seperti (6,600) adalah POTONGAN HARGA — JANGAN masukkan sebagai item. Jumlahkan SEMUA potongan ke summary.discount sebagai angka positif.\n"
            "- Baris 'ANDA HEMAT' menunjukkan total penghematan/diskon — gunakan sebagai konfirmasi summary.discount, bukan sebagai kembalian.\n"
            "- Jumlah seluruh item.subtotal seharusnya sama dengan Subtotal/Total yang tertera. Jika hasil penjumlahanmu jauh lebih besar dari total tertera, kemungkinan kamu tertukar unit_price dengan subtotal — perbaiki.\n"
            "- summary.total = nominal akhir yang BENAR-BENAR DIBAYAR (cari baris seperti 'TOTAL BELANJA', 'NON TUNAI', 'TUNAI', 'TOTAL BAYAR', 'BAYAR'); gunakan nilai itu apa adanya.\n"
            "- PPN/pajak pada struk ritel/minimarket (Indomaret, Alfamart, dll) SUDAH TERMASUK dalam harga jual — baris 'PPN', 'DPP', 'PB1' hanya rincian informatif. Isi summary.tax = null. Isi summary.tax dengan angka HANYA jika pajak jelas DITAMBAHKAN di atas subtotal (mis. restoran yang menulis '+PB1 10%' terpisah).\n"
            "- Baris 'HARGA JUAL' pada struk minimarket adalah harga sebelum diskon — BUKAN total yang dibayar. Abaikan untuk summary.total.\n"
            "- Abaikan baris yang jelas bukan data transaksi (mis. ucapan terima kasih, jam buka, alamat website, QR code, nomor referensi)."
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Kamu adalah AI ekstraktor struk belanja dari teks hasil OCR."},
                {
                    "role": "user",
                    "content": f"{RECEIPT_EXTRACTION_PROMPT}{ocr_instruction}\n\nBerikut teks hasil OCR dari struk:\n\n{ocr_text}",
                },
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
        }

    def _build_vision_payload(self, image_path: str) -> dict[str, Any]:
        processed = preprocess_for_vlm(image_path)
        target = processed or image_path
        try:
            with open(target, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
        finally:
            if processed:
                try:
                    os.unlink(processed)
                except OSError:
                    pass

        vision_instruction = (
            "\n\nATURAN TAMBAHAN untuk foto struk:\n"
            "- Kamu melihat foto struk langsung. Baca semua item, harga, dan total dengan teliti.\n"
            "- PENTING: Angka harga di KANAN setiap baris item adalah SUBTOTAL BARIS (sudah termasuk kuantitas), BUKAN harga satuan. Isikan langsung ke item.subtotal. Hitung unit_price = subtotal / quantity. JANGAN mengalikan harga dengan quantity.\n"
            "- Validasi: jumlah semua item.subtotal harus SAMA dengan Total/Subtotal yang tertera di struk. Jika tidak cocok, kemungkinan kamu salah mengalikan — perbaiki.\n"
            "- Baris VOUCHER/DISKON/angka dalam tanda kurung (mis. (6,600)) adalah potongan harga — JUMLAHKAN SEMUA potongan ke summary.discount sebagai satu angka positif. JANGAN masukkan sebagai item.\n"
            "- summary.total = nominal akhir yang BENAR-BENAR DIBAYAR (TOTAL BELANJA / NON TUNAI / TUNAI / Total Bayar).\n"
            "- PPN pada struk ritel/minimarket (Indomaret, Alfamart) SUDAH TERMASUK dalam harga → isi summary.tax = null. TAPI jika ada baris 'Pajak'/'Tax'/'PB1' yang DITAMBAHKAN terpisah (Subtotal + Pajak = Total, umum di restoran/cafe), isi summary.tax dengan angka pajak tersebut.\n"
            "- Baris 'HARGA JUAL' bukan total bayar. Abaikan.\n"
            "- 'ANDA HEMAT' menunjukkan total penghematan — ini SAMA dengan summary.discount. JANGAN isi ke service_charge. service_charge = null kecuali ada baris eksplisit 'service charge' atau 'biaya layanan'.\n"
            "- summary.subtotal = jumlah semua item.subtotal SEBELUM dikurangi voucher/diskon.\n"
            "- Rumus: summary.total = summary.subtotal - summary.discount."
        )
        return {
            "model": self.model,
            "messages": [
                {"role": "system", "content": "Kamu adalah AI ekstraktor struk belanja dari foto."},
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                        {"type": "text", "text": f"{RECEIPT_EXTRACTION_PROMPT}{vision_instruction}"},
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
