from __future__ import annotations


class ExtractionError(Exception):
    """Raised when the receipt extractor fails to obtain a response."""


class TranscriptionError(RuntimeError):
    """Raised when voice transcription fails.

    Subclasses RuntimeError to stay backward compatible with callers that
    catch RuntimeError.
    """
