from __future__ import annotations

import logging
import tempfile

from PIL import Image, ImageFilter, ImageOps

logger = logging.getLogger(__name__)


class PaddleOCREngine:
    """Wrapper PaddleOCR 3.x untuk membaca teks dari gambar struk (lazy load model).

    extract_text() merekonstruksi tata letak: deteksi yang berada pada baris vertikal
    yang sama digabung (diurutkan kiri→kanan) agar nama item tetap sebaris dengan harga.
    """

    def __init__(self, lang: str = "id", use_textline_orientation: bool = True) -> None:
        self.lang = lang
        self.use_textline_orientation = use_textline_orientation
        self._ocr = None

    def _build(self, lang: str):
        from paddleocr import PaddleOCR

        # enable_mkldnn=False mencegah crash oneDNN (ConvertPirAttribute2RuntimeAttribute) di paddlepaddle 3.x CPU.
        # text_rec_score_thresh=0.5 membuang hasil low-confidence (noise) agar tidak mengganggu interpretasi llama.
        return PaddleOCR(
            lang=lang,
            use_textline_orientation=self.use_textline_orientation,
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            enable_mkldnn=False,
            text_rec_score_thresh=0.5,
        )

    def _get_ocr(self):
        if self._ocr is None:
            try:
                self._ocr = self._build(self.lang)
            except Exception:
                logger.warning("PaddleOCR lang=%r tidak didukung, fallback ke 'latin'", self.lang)
                self._ocr = self._build("latin")
        return self._ocr

    def extract_text(self, image_path: str) -> str:
        """Jalankan OCR (.predict) dan kembalikan teks dengan tata letak baris terjaga."""
        processed_path = self._preprocess_image(image_path)
        try:
            return self._run_ocr(processed_path or image_path)
        finally:
            if processed_path:
                import os
                try:
                    os.unlink(processed_path)
                except OSError:
                    pass

    def _run_ocr(self, image_path: str) -> str:
        entries: list[tuple[float, float, float, str]] = []  # (x_left, y_top, y_bottom, text)
        for res in self._get_ocr().predict(image_path) or []:
            texts = res.get("rec_texts") or []
            for (x_left, y_top, y_bottom), text in zip(self._boxes(res), texts):
                if text:
                    entries.append((x_left, y_top, y_bottom, str(text)))
        entries = self._filter_noise(entries)
        return self._layout_text(entries)

    @staticmethod
    def _preprocess_image(image_path: str) -> str | None:
        """Grayscale + autocontrast + sharpen untuk mengurangi efek shadow."""
        try:
            img = Image.open(image_path)
            img = ImageOps.grayscale(img)
            img = ImageOps.autocontrast(img, cutoff=1)
            img = img.filter(ImageFilter.SHARPEN)
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            img.save(tmp.name)
            return tmp.name
        except Exception:
            logger.debug("Preprocessing gagal, gunakan gambar asli", exc_info=True)
            return None

    @staticmethod
    def _boxes(res) -> list[tuple[float, float, float]]:
        """Kembalikan (x_left, y_top, y_bottom) per deteksi, selaras urutan rec_texts."""
        out: list[tuple[float, float, float]] = []
        boxes = res.get("rec_boxes")
        if boxes is not None and len(boxes):
            for b in boxes:
                b = [float(v) for v in b]
                out.append((b[0], b[1], b[3]))
            return out
        for poly in res.get("rec_polys") or []:
            xs = [float(p[0]) for p in poly]
            ys = [float(p[1]) for p in poly]
            out.append((min(xs), min(ys), max(ys)))
        return out

    @staticmethod
    def _filter_noise(entries: list[tuple[float, float, float, str]]) -> list[tuple[float, float, float, str]]:
        """Buang deteksi pendek (≤3 char) yang berada di luar area x utama struk (noise latar)."""
        if len(entries) < 5:
            return entries
        x_lefts = sorted(e[0] for e in entries)
        q1 = x_lefts[len(x_lefts) // 4]
        q3 = x_lefts[3 * len(x_lefts) // 4]
        iqr = q3 - q1
        x_max_bound = q3 + 1.5 * iqr
        return [e for e in entries if len(e[3].strip()) > 3 or e[0] <= x_max_bound]

    @staticmethod
    def _layout_text(entries: list[tuple[float, float, float, str]]) -> str:
        if not entries:
            return ""
        entries.sort(key=lambda e: (e[1], e[0]))
        heights = sorted(e[2] - e[1] for e in entries)
        med_h = heights[len(heights) // 2] or 1.0
        tol = med_h * 0.6

        rows: list[list[tuple[float, str]]] = []
        cur: list[tuple[float, str]] = []
        anchor_y: float | None = None
        for x_left, y_top, y_bottom, text in entries:
            yc = (y_top + y_bottom) / 2
            if anchor_y is None or abs(yc - anchor_y) <= tol:
                cur.append((x_left, text))
                if anchor_y is None:
                    anchor_y = yc
            else:
                rows.append(cur)
                cur = [(x_left, text)]
                anchor_y = yc
        if cur:
            rows.append(cur)

        # Merge orphan value lines: jika baris hanya berisi angka dan baris sebelumnya
        # berakhir ':', gabungkan ke baris sebelumnya.
        import re
        merged: list[list[tuple[float, str]]] = []
        for row in rows:
            texts_only = " ".join(t[1] for t in row).strip()
            if merged and re.fullmatch(r"[\d.,() ]+", texts_only):
                prev_text = " ".join(t[1] for t in merged[-1]).strip()
                if prev_text.endswith(":"):
                    merged[-1].extend(row)
                    continue
            merged.append(row)

        lines = []
        for row in merged:
            row.sort(key=lambda t: t[0])
            lines.append("  ".join(t[1] for t in row))
        return "\n".join(lines)
