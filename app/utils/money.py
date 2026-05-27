from __future__ import annotations

import re


def normalize_amount(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(round(value))

    text = str(value).strip()
    if not text:
        return None

    digits = re.sub(r"[^0-9-]", "", text)
    if digits in {"", "-"}:
        return None

    try:
        return int(digits)
    except ValueError:
        return None


def format_rupiah(value) -> str:
    amount = normalize_amount(value)
    if amount is None:
        return "Rp -"
    return f"Rp {amount:,.0f}".replace(",", ".")

