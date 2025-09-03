"""Whisper Wayland - Transcription Client Module

Audio transcription components using OpenAI Whisper API.
"""

from whisper_wayland.transcription_client.transcription_client import (
    TranscriptionClient,
    TranscriptionError,
)

__all__ = ["TranscriptionClient", "TranscriptionError"]
