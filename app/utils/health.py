from __future__ import annotations

import logging

import httpx

logger = logging.getLogger(__name__)


async def check_server_health(name: str, url: str, timeout: int = 5) -> bool:
    """Check if a server is reachable. Returns True if healthy."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url)
            healthy = response.status_code < 500
            if healthy:
                logger.info("%s is reachable at %s", name, url)
            else:
                logger.warning("%s returned HTTP %d at %s", name, response.status_code, url)
            return healthy
    except Exception as exc:
        logger.warning("%s is not reachable at %s: %s", name, url, exc)
        return False


async def check_all_services(llamacpp_base_url: str, whisper_base_url: str) -> dict[str, bool]:
    """Check health of all AI services."""
    llama_url = f"{llamacpp_base_url.rstrip('/')}/models"
    whisper_url = f"{whisper_base_url.rstrip('/')}/health"

    llama_ok = await check_server_health("llama-server", llama_url)
    whisper_ok = await check_server_health("whisper-server", whisper_url)

    return {"llama": llama_ok, "whisper": whisper_ok}
