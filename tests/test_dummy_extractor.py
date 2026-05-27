import pytest
from pathlib import Path

from app.ai.receipt_extractor import DummyReceiptExtractor


@pytest.mark.asyncio
async def test_dummy_extractor_returns_success(tmp_path: Path) -> None:
    image_path = tmp_path / "receipt.jpg"
    image_path.write_bytes(b"fake-image")

    extractor = DummyReceiptExtractor()
    result = await extractor.extract(str(image_path))

    assert result["status"] == "success"
    assert result["store"]["name"] == "Dummy Store"
    assert result["summary"]["total"] == 60000
