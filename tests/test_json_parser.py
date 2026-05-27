from app.utils.json_utils import extract_json_from_text, remove_code_fence, safe_parse_json


def test_remove_code_fence_json_block() -> None:
    text = """```json
{"status":"success","summary":{"total":35000}}
```"""
    assert remove_code_fence(text) == '{"status":"success","summary":{"total":35000}}'


def test_extract_json_from_wrapped_text() -> None:
    text = """
Model output:
```json
{"status":"partial","summary":{"total":20000}}
```
"""
    parsed = extract_json_from_text(text)
    assert parsed["status"] == "partial"
    assert parsed["summary"]["total"] == 20000


def test_safe_parse_json_invalid() -> None:
    assert safe_parse_json("bukan json") == {}

