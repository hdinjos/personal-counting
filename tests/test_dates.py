from datetime import date, datetime, time

from app.utils.dates import parse_receipt_date, parse_receipt_time


def test_parse_receipt_date_full_formats() -> None:
    assert parse_receipt_date("2026-05-27") == date(2026, 5, 27)
    assert parse_receipt_date("27-05-2026") == date(2026, 5, 27)
    assert parse_receipt_date("27/05/2026") == date(2026, 5, 27)
    assert parse_receipt_date("27.05.2026") == date(2026, 5, 27)
    assert parse_receipt_date("27-05-26") == date(2026, 5, 27)


def test_parse_receipt_date_day_month_uses_current_year() -> None:
    assert parse_receipt_date("27/05", current_year=2024) == date(2024, 5, 27)


def test_parse_receipt_date_passthrough_and_none() -> None:
    assert parse_receipt_date(date(2026, 5, 27)) == date(2026, 5, 27)
    assert parse_receipt_date(datetime(2026, 5, 27, 10, 0)) == date(2026, 5, 27)
    assert parse_receipt_date(None) is None
    assert parse_receipt_date("") is None
    assert parse_receipt_date("bukan tanggal") is None


def test_parse_receipt_time_formats() -> None:
    assert parse_receipt_time("10:15") == time(10, 15)
    assert parse_receipt_time("10.15") == time(10, 15)
    assert parse_receipt_time("10:15:30") == time(10, 15)


def test_parse_receipt_time_passthrough_and_none() -> None:
    assert parse_receipt_time(time(9, 0)) == time(9, 0)
    assert parse_receipt_time(None) is None
    assert parse_receipt_time("") is None
    assert parse_receipt_time("bukan jam") is None
