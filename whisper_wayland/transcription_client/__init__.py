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
from whisper_wayland.transcription_client.transcription_engine import (
    TimestampedTranscriptionResult,
    WordTimestamp,
)

__all__ = [
    "RealtimeStreamingTranscriptionClient",
    "StreamingTranscriptionResult",
    "TimestampedTranscriptionResult",
    "TranscriptionBackendMetadata",
    "TranscriptionClient",
    "TranscriptionError",
    "WordTimestamp",
]
