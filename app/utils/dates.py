from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo


BULAN_INDONESIA = [
    "", "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]


def format_date_id(value: date | str | None, t: time | None = None) -> str:
    """Format date ke '30 Mei 2026 10:15'. Jika time None, tanpa jam."""
    if value is None:
        return "-"
    if isinstance(value, str):
        parsed = parse_receipt_date(value)
        if parsed is None:
            return value
        value = parsed
    result = f"{value.day} {BULAN_INDONESIA[value.month]} {value.year}"
    if t is not None:
        result += f" {t.strftime('%H:%M')} WIB"
    return result


def format_month_id(year: int, month: int) -> str:
    """Format bulan ke 'Mei 2026'."""
    return f"{BULAN_INDONESIA[month]} {year}"


def today_local_date(timezone: str = "Asia/Jakarta") -> date:
    return datetime.now(ZoneInfo(timezone)).date()


def now_local_time(timezone: str = "Asia/Jakarta") -> time:
    return datetime.now(ZoneInfo(timezone)).time().replace(second=0, microsecond=0)


def month_from_date(value: date) -> tuple[int, int]:
    return value.year, value.month


def month_date_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        end = date(year + 1, 1, 1)
    else:
        end = date(year, month + 1, 1)
    return start, end


def parse_receipt_date(value, current_year: int | None = None) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value

    text = str(value).strip()
    if not text:
        return None

    full_formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%d.%m.%Y",
        "%d-%m-%y",
        "%d/%m/%y",
    ]
    for fmt in full_formats:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    day_month_formats = ["%d-%m", "%d/%m", "%d.%m"]
    for fmt in day_month_formats:
        try:
            parsed = datetime.strptime(text, fmt)
            year = current_year or date.today().year
            return parsed.replace(year=year).date()
        except ValueError:
            continue

    return None


def parse_receipt_time(value) -> time | None:
    if value is None:
        return None
    if isinstance(value, time):
        return value

    text = str(value).strip()
    if not text:
        return None

    formats = ["%H:%M", "%H.%M", "%H:%M:%S"]
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).time().replace(second=0, microsecond=0)
        except ValueError:
            continue

    return None

