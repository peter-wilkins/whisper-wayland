"""Whisper Wayland - Transcription Client Module

Audio transcription components using OpenAI Whisper API.
"""

from whisper_wayland.transcription_client.realtime_streaming_client import (
    RealtimeStreamingTranscriptionClient,
    StreamingTranscriptionResult,
)
from whisper_wayland.transcription_client.transcription_client import (
    TranscriptionBackendMetadata,
    TranscriptionClient,
    TranscriptionError,
)

__all__ = [
    "RealtimeStreamingTranscriptionClient",
    "StreamingTranscriptionResult",
    "TranscriptionBackendMetadata",
    "TranscriptionClient",
    "TranscriptionError",
]
