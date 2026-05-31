import asyncio

import app.utils.health as health_mod
from app.utils.health import check_all_services


def test_check_all_services_maps_results(monkeypatch) -> None:
    calls = []

    async def fake_check(name, url, timeout=5):
        calls.append((name, url))
        return name == "llama-server"

    monkeypatch.setattr(health_mod, "check_server_health", fake_check)

    results = asyncio.run(
        check_all_services("http://llama:8000/v1", "http://whisper:8001")
    )

    assert results == {"llama": True, "whisper": False}
    assert len(calls) == 2
    assert calls[0][1].endswith("/models")
    assert calls[1][1].endswith("/health")
