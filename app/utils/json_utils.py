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


def extract_json_from_text(text: str) -> dict:
    cleaned = remove_code_fence(text)

    direct = safe_parse_json(cleaned)
    if direct:
        return direct

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", cleaned):
        start = match.start()
        try:
            obj, _ = decoder.raw_decode(cleaned[start:])
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            return obj

    return {}

