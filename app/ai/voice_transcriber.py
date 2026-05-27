from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx


class VoiceTranscriber:
    def __init__(
        self,
        base_url: str,
        inference_path: str = "/inference",
        timeout_seconds: int = 120,
        language: str = "id",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.inference_path = inference_path if inference_path.startswith("/") else f"/{inference_path}"
        self.timeout_seconds = timeout_seconds
        self.language = language

    async def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file via whisper.cpp whisper-server."""
        audio_file = Path(audio_path)
        if not audio_file.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        mime_type, _ = mimetypes.guess_type(audio_file.name)
        content_type = mime_type or "application/octet-stream"
        url = f"{self.base_url}{self.inference_path}"

        try:
            with audio_file.open("rb") as file_obj:
                files = [
                    ("file", (audio_file.name, file_obj, content_type)),
                    ("language", (None, self.language)),
                    ("response_format", (None, "json")),
                ]

                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(url, files=files)
        except httpx.TimeoutException as exc:
            raise RuntimeError("whisper-server request timed out") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"whisper-server request failed: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text.strip()
            message = f"whisper-server returned HTTP {response.status_code}"
            if detail:
                message += f": {detail}"
            if response.status_code == 400 and audio_file.suffix.lower() != ".wav":
                message += (
                    " (Hint: Telegram voice note biasanya .ogg/opus. Jalankan whisper-server dengan --convert "
                    "dan pastikan ffmpeg tersedia, atau konversi audio ke WAV sebelum dikirim.)"
                )
            raise RuntimeError(message)

        try:
            payload = response.json()
        except ValueError as exc:
            raise RuntimeError("Invalid JSON response from whisper-server") from exc

        if not isinstance(payload, dict):
            raise RuntimeError("Unexpected response type from whisper-server")

        error_message = payload.get("error")
        if isinstance(error_message, str) and error_message.strip():
            raise RuntimeError(f"whisper-server error: {error_message.strip()}")

        text = payload.get("text")
        if not isinstance(text, str):
            return ""

        return text.strip()
