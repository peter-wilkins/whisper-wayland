"""Tests for transcription audio preparation."""

from __future__ import annotations

import io
import os
import unittest.mock
import wave

import whisper_wayland as ww
from whisper_wayland.application.audio_processor import AudioProcessor
from whisper_wayland.silero_vad import VadResult, VadSegment


class FakeTranscriptionClient:
    """Small fake transcription client for audio processor tests."""

    def __init__(self, config: ww.Config) -> None:
        """Create fake client."""
        self.config = config
        self.audio_data = b""
        self.last_transcription_backend = ww.TranscriptionBackendMetadata(
            provider="fake",
            processor_id="fake",
        )

    def transcribe_audio(self, audio_data: bytes) -> str:
        """Record uploaded bytes and return text."""
        self.audio_data = audio_data
        return "raw text"

    def post_process_text(self, text: str) -> str:
        """Return text unchanged."""
        return text


class FakeSileroVad:
    """Fake Silero VAD preprocessor."""

    def __init__(self) -> None:
        """Create fake VAD."""
        self.audio_data = b""

    def filter_audio(self, audio_data: bytes, filename: str | None = None) -> VadResult:
        """Return deterministic speech-only audio."""
        self.audio_data = audio_data
        return VadResult(
            audio_data=b"speech-only",
            content_type="audio/ogg",
            filename_suffix=".silero.ogg",
            raw_duration_seconds=1.5,
            speech_duration_seconds=0.5,
            segments=[VadSegment(start_seconds=0.2, end_seconds=0.7)],
            threshold=0.5,
            model_path="fake.onnx",
        )


def test_audio_processor_auto_vad_skips_short_recordings() -> None:
    with unittest.mock.patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-test123",
            "AUDIO_TRANSCRIPTION_VAD_MODE": "auto",
            "TRANSCRIPTION_VAD_AUTO_MIN_DURATION_SECONDS": "1",
        },
        clear=True,
    ):
        config = ww.Config("/nonexistent/test.env")
        client = FakeTranscriptionClient(config)
        vad = FakeSileroVad()
        processor = AudioProcessor(client, silero_vad=vad)  # type: ignore[arg-type]
        short_audio = _test_wav(duration_seconds=0.5)

        result = processor.transcribe_audio_with_result(short_audio)

    assert result is not None
    assert client.audio_data == short_audio
    assert vad.audio_data == b""


def test_audio_processor_auto_vad_filters_long_recordings() -> None:
    with unittest.mock.patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-test123",
            "AUDIO_TRANSCRIPTION_VAD_MODE": "auto",
            "TRANSCRIPTION_VAD_AUTO_MIN_DURATION_SECONDS": "1",
        },
        clear=True,
    ):
        config = ww.Config("/nonexistent/test.env")
        client = FakeTranscriptionClient(config)
        vad = FakeSileroVad()
        processor = AudioProcessor(client, silero_vad=vad)  # type: ignore[arg-type]
        long_audio = _test_wav(duration_seconds=1.5)

        result = processor.transcribe_audio_with_result(long_audio)

    assert result is not None
    assert vad.audio_data == long_audio
    assert client.audio_data == b"speech-only"


def _test_wav(*, duration_seconds: float, sample_rate: int = 16000) -> bytes:
    frame_count = int(duration_seconds * sample_rate)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()
