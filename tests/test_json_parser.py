from app.utils.json_utils import (
    _eval_arithmetic_values,
    extract_json_from_text,
    remove_code_fence,
    safe_parse_json,
)


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


def test_eval_arithmetic_addition() -> None:
    assert _eval_arithmetic_values("6600 + 2300 + 3000") == "11900"


def test_eval_arithmetic_subtraction() -> None:
    assert _eval_arithmetic_values("13700 - 700") == "13000"


def test_eval_arithmetic_leaves_non_expression_untouched() -> None:
    assert _eval_arithmetic_values("total adalah 5000") == "total adalah 5000"


def test_extract_json_evaluates_arithmetic_value() -> None:
    text = '{"status":"success","summary":{"total":6600 + 2300}}'
    parsed = extract_json_from_text(text)
    assert parsed["summary"]["total"] == 8900


