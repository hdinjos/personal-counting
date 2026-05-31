from app.utils.money import format_rupiah, normalize_amount


def test_normalize_amount_none_and_empty() -> None:
    assert normalize_amount(None) is None
    assert normalize_amount("") is None
    assert normalize_amount("   ") is None
    assert normalize_amount("-") is None


def test_normalize_amount_bool_rejected() -> None:
    assert normalize_amount(True) is None
    assert normalize_amount(False) is None


def test_normalize_amount_int_and_float() -> None:
    assert normalize_amount(15000) == 15000
    assert normalize_amount(15000.4) == 15000
    assert normalize_amount(15000.6) == 15001


def test_normalize_amount_string_with_separators() -> None:
    assert normalize_amount("Rp 15.000") == 15000
    assert normalize_amount("13,700") == 13700


def test_normalize_amount_negative_preserved() -> None:
    assert normalize_amount("-5000") == -5000


def test_normalize_amount_non_numeric() -> None:
    assert normalize_amount("abc") is None


def test_format_rupiah() -> None:
    assert format_rupiah(15000) == "Rp 15.000"
    assert format_rupiah(None) == "Rp -"
