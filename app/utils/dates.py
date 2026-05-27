from __future__ import annotations

from datetime import date, datetime, time
from zoneinfo import ZoneInfo


def today_local_date(timezone: str = "Asia/Jakarta") -> date:
    return datetime.now(ZoneInfo(timezone)).date()


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

