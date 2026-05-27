import asyncio
import whisper

class VoiceTranscriber:
    def __init__(self, model_name: str = "tiny"):
        self.model_name = model_name
        self.model = None

    def _load_model(self) -> None:
        if self.model is None:
            self.model = whisper.load_model(self.model_name)

    async def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file to text using Whisper."""
        def _run() -> str:
            self._load_model()
            # Force language to Indonesian for better accuracy with local receipts
            result = self.model.transcribe(audio_path, language="id")
            return result.get("text", "").strip()

        return await asyncio.to_thread(_run)
