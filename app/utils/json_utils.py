from __future__ import annotations

import json
import re


def remove_code_fence(text: str) -> str:
    stripped = text.strip()
    if not stripped:
        return stripped

    fenced_block = re.search(r"```(?:json)?\s*(.*?)\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fenced_block:
        return fenced_block.group(1).strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines:
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    return stripped


def safe_parse_json(text: str) -> dict:
    cleaned = text.strip()
    if not cleaned:
        return {}
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _safe_eval_additive(expr: str) -> int:
    """Evaluasi ekspresi penjumlahan/pengurangan bilangan bulat tanpa eval()."""
    tokens = re.findall(r"[+\-]?\s*\d+", expr)
    return sum(int(re.sub(r"\s+", "", t)) for t in tokens)


def _eval_arithmetic_values(text: str) -> str:
    """Ganti ekspresi aritmatika sederhana (mis. '13700 + 25500 + 8200') dengan hasilnya."""
    def _eval_match(m: re.Match) -> str:
        expr = m.group(0)
        try:
            # Hanya izinkan digit, +, -, spasi
            if re.fullmatch(r"[\d+\-\s]+", expr):
                return str(_safe_eval_additive(expr))
        except Exception:
            pass
        return expr

    return re.sub(r"\d+(?:\s*[+\-]\s*\d+)+", _eval_match, text)


def extract_json_from_text(text: str) -> dict:
    cleaned = remove_code_fence(text)

    direct = safe_parse_json(cleaned)
    if direct:
        return direct

    # Coba evaluasi ekspresi aritmatika (model VLM kadang menulis '6600 + 2300 + 3000')
    evaluated = _eval_arithmetic_values(cleaned)
    if evaluated != cleaned:
        direct = safe_parse_json(evaluated)
        if direct:
            return direct

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", evaluated):
        start = match.start()
        try:
            obj, _ = decoder.raw_decode(evaluated[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj

    return {}
