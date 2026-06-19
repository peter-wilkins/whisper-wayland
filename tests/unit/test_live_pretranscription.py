"""Tests for opt-in live pre-transcription chunking."""

from __future__ import annotations

import io
import os
import unittest.mock
import wave
from types import SimpleNamespace

import whisper_wayland as ww
from whisper_wayland.application.live_pretranscription import (
    LivePretranscriptionSession,
    PretranscribedAudioResult,
)
from whisper_wayland.application.transcription_processor import TranscriptionProcessor
from whisper_wayland.silero_vad import VadAudioChunk, VadSegment, VadSplitResult


class FakeSileroVad:
    """Return deterministic phrase chunks for a growing recording."""

    def split_audio(self, audio_data: bytes, *_args: object, **_kwargs: object) -> VadSplitResult:
        chunks = [
            _chunk(1, 8, b"early"),
            _chunk(10, 14, b"late"),
        ]
        return VadSplitResult(
            raw_duration_seconds=15 if audio_data == b"snapshot" else 16,
            chunks=chunks,
            threshold=0.5,
            model_path="fake.onnx",
        )


class FakeTranscriptionClient:
    """Record chunk uploads and return deterministic text."""

    def __init__(self) -> None:
        self.calls: list[bytes] = []
        self.last_transcription_backend = ww.TranscriptionBackendMetadata(
            provider="openai",
            processor_id="whisper-1",
        )

    def transcribe_audio(self, audio_data: bytes) -> str | None:
        self.calls.append(audio_data)
        return {b"early": "Early thought.", b"late": "Late thought."}[audio_data]


def test_live_pretranscription_reuses_stable_chunk_and_uses_chunk_provider_config() -> None:
    config = _live_config()
    client = FakeTranscriptionClient()
    factory_configs = []
    session = LivePretranscriptionSession(
        config,
        lambda: b"snapshot",
        silero_vad=FakeSileroVad(),  # type: ignore[arg-type]
        client_factory=lambda chunk_config: factory_configs.append(chunk_config) or client,
    )

    session.poll()
    result = session.complete(b"complete")

    assert client.calls == [b"early", b"late"]
    assert factory_configs[0].whisper_model == "whisper-1"
    assert factory_configs[0].transcription_race_models == []
    assert result == PretranscribedAudioResult(
        raw_text="Early thought. Late thought.",
        transcription_provider="openai",
        transcription_processor_id="whisper-1",
        chunk_count=2,
    )


def test_live_pretranscription_falls_back_when_a_final_chunk_has_no_text() -> None:
    config = _live_config()
    client = FakeTranscriptionClient()
    client.transcribe_audio = unittest.mock.Mock(side_effect=["Early thought.", None])
    session = LivePretranscriptionSession(
        config,
        lambda: b"snapshot",
        silero_vad=FakeSileroVad(),  # type: ignore[arg-type]
        client_factory=lambda _chunk_config: client,
    )

    session.poll()

    assert session.complete(b"complete") is None


def test_transcription_processor_uses_completed_live_transcript_without_batch_upload() -> None:
    with unittest.mock.patch.dict(
        os.environ,
        {
            "OPENAI_API_KEY": "sk-test123",
            "PRETRANSCRIPTION_CHUNKING_ENABLED": "true",
        },
        clear=True,
    ):
        config = ww.Config("/nonexistent/test.env")
        transcription_client = unittest.mock.Mock()
        transcription_client.config = config
        transcription_client.post_process_text.return_value = "Clean final thought."
        text_inserter = unittest.mock.Mock()
        processor = TranscriptionProcessor(transcription_client, text_inserter)
        session = unittest.mock.Mock()
        session.complete.return_value = PretranscribedAudioResult(
            raw_text="raw final thought",
            transcription_provider="openai",
            transcription_processor_id="whisper-1",
            chunk_count=2,
        )
        processor._live_pretranscription = session

        processor.process_audio(_audible_wav())

    session.complete.assert_called_once()
    transcription_client.transcribe_audio.assert_not_called()
    transcription_client.post_process_text.assert_called_once_with("raw final thought")
    text_inserter.insert_text.assert_called_once_with("Clean final thought.")


def _live_config() -> SimpleNamespace:
    return SimpleNamespace(
        whisper_model="deepgram:nova-3",
        transcription_race_models=["whispercpp:http://127.0.0.1:2022/inference"],
        pretranscription_chunk_whisper_model="whisper-1",
        pretranscription_chunk_race_models=[],
        pretranscription_chunk_min_recording_seconds=10.0,
        pretranscription_chunk_poll_interval_seconds=2.0,
        pretranscription_chunk_stable_tail_seconds=3.0,
        pretranscription_chunk_coalesce_min_duration_seconds=4.0,
        pretranscription_chunk_coalesce_max_duration_seconds=12.0,
        pretranscription_chunk_coalesce_max_gap_seconds=3.0,
    )


def _chunk(start_seconds: float, end_seconds: float, audio_data: bytes) -> VadAudioChunk:
    return VadAudioChunk(
        segment=VadSegment(start_seconds=start_seconds, end_seconds=end_seconds),
        audio_data=audio_data,
        content_type="audio/ogg",
        filename_suffix=".ogg",
    )


def _audible_wav() -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(16000)
        wav_file.writeframes(b"\xa0\x0f" * 1600)
    return buffer.getvalue()
