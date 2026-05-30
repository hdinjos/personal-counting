from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class PaddleOCREngine:
    """Wrapper PaddleOCR untuk membaca teks dari gambar struk (lazy load model)."""

    def __init__(self, lang: str = "id", use_angle_cls: bool = True) -> None:
        self.lang = lang
        self.use_angle_cls = use_angle_cls
        self._ocr = None

    def _get_ocr(self):
        if self._ocr is None:
            from paddleocr import PaddleOCR

            self._ocr = PaddleOCR(use_angle_cls=self.use_angle_cls, lang=self.lang, show_log=False)
        return self._ocr

    def extract_text(self, image_path: str) -> str:
        """Jalankan OCR dan kembalikan teks gabungan (satu baris per deteksi)."""
        result = self._get_ocr().ocr(image_path, cls=self.use_angle_cls)
        
        lines: list[str] = []
        for page in result or []:
            for entry in page or []:
                try:
                    text = entry[1][0]
                except (IndexError, TypeError):
                    continue
                if text:
                    lines.append(str(text))
        return "\n".join(lines)
