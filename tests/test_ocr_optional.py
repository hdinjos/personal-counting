import sys

import pytest

from app.ai.ocr import PaddleOCREngine


def test_paddleocr_not_imported_on_init() -> None:
    engine = PaddleOCREngine(lang="id")
    assert engine._ocr is None


def test_missing_paddleocr_raises_informative(monkeypatch) -> None:
    # Simulate the package being absent.
    monkeypatch.setitem(sys.modules, "paddleocr", None)
    engine = PaddleOCREngine(lang="id")

    with pytest.raises(RuntimeError, match="paddleocr"):
        engine._get_ocr()
