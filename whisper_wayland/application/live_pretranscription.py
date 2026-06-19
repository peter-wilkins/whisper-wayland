"""Feature-flagged live Silero chunk transcription for long recordings."""

from __future__ import annotations

import logging
import threading
import typing
from dataclasses import dataclass

from whisper_wayland.pretranscription import (
    ChunkTranscriptionConfig,
    chunk_transcription_config,
)
from whisper_wayland.silero_vad import SileroVadPreprocessor, VadAudioChunk, VadSplitResult
from whisper_wayland.transcription_client import TranscriptionClient

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PretranscribedAudioResult:
    """Complete transcript assembled from ordered live speech chunks."""

    raw_text: str
    transcription_provider: str | None
    transcription_processor_id: str | None
    chunk_count: int


@dataclass(frozen=True)
class _ChunkTranscript:
    text: str
    transcription_provider: str | None
    transcription_processor_id: str | None


class LivePretranscriptionSession:
    """Transcribe stable speech chunks before the push-to-talk key is released."""

    def __init__(
        self,
        config: typing.Any,
        snapshot_audio: typing.Callable[[], bytes | None],
        *,
        silero_vad: SileroVadPreprocessor | None = None,
        client_factory: typing.Callable[[ChunkTranscriptionConfig], typing.Any] | None = None,
    ) -> None:
        """Create an opt-in session around a recorder audio snapshot function."""
        self._snapshot_audio = snapshot_audio
        self._silero_vad = silero_vad or SileroVadPreprocessor()
        self._client_factory = client_factory or TranscriptionClient
        self._chunk_config = chunk_transcription_config(config)
        self._min_recording_seconds = config.pretranscription_chunk_min_recording_seconds
        self._poll_interval_seconds = config.pretranscription_chunk_poll_interval_seconds
        self._stable_tail_seconds = config.pretranscription_chunk_stable_tail_seconds
        self._coalesce_min_duration_seconds = (
            config.pretranscription_chunk_coalesce_min_duration_seconds
        )
        max_duration = config.pretranscription_chunk_coalesce_max_duration_seconds
        self._coalesce_max_duration_seconds = max_duration if max_duration > 0 else None
        self._coalesce_max_gap_seconds = config.pretranscription_chunk_coalesce_max_gap_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._transcripts: dict[tuple[float, float], _ChunkTranscript] = {}
        self._client: typing.Any = None

    def start(self) -> None:
        """Start polling recorded audio after the configured duration threshold."""
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            name="whisper-wayland-pretranscription",
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        """Stop polling without returning a transcript."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()

    def complete(self, audio_data: bytes) -> PretranscribedAudioResult | None:
        """Finish remaining chunks and return one transcript, or None for batch fallback."""
        self._stop_event.set()
        if self._thread:
            self._thread.join()

        split_result = self._split(audio_data)
        if not split_result or not split_result.chunks:
            return None
        if not self._transcribe_missing(split_result.chunks):
            return None

        transcripts = []
        for chunk in split_result.chunks:
            transcript = self._transcript_for(chunk)
            if transcript is None:
                return None
            transcripts.append(transcript)

        raw_text = " ".join(item.text.strip() for item in transcripts if item.text.strip())
        if not raw_text:
            return None
        providers = {item.transcription_provider for item in transcripts}
        processor_ids = {item.transcription_processor_id for item in transcripts}
        return PretranscribedAudioResult(
            raw_text=raw_text,
            transcription_provider=providers.pop() if len(providers) == 1 else "multiple",
            transcription_processor_id=(
                processor_ids.pop() if len(processor_ids) == 1 else "multiple"
            ),
            chunk_count=len(transcripts),
        )

    def poll(self) -> None:
        """Process currently stable chunks once; exposed for deterministic tests."""
        audio_data = self._snapshot_audio()
        if not audio_data:
            return
        split_result = self._split(audio_data)
        if not split_result or split_result.raw_duration_seconds < self._min_recording_seconds:
            return
        stable_end = split_result.raw_duration_seconds - self._stable_tail_seconds
        stable_chunks = [
            chunk for chunk in split_result.chunks if chunk.segment.end_seconds <= stable_end
        ]
        self._transcribe_missing(stable_chunks)

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.poll()
            except Exception as e:
                _logger.warning("Live pre-transcription poll failed: %s", e)
            self._stop_event.wait(self._poll_interval_seconds)

    def _split(self, audio_data: bytes) -> VadSplitResult | None:
        try:
            return self._silero_vad.split_audio(
                audio_data,
                "recording.wav",
                min_chunk_duration_seconds=self._coalesce_min_duration_seconds,
                max_chunk_duration_seconds=self._coalesce_max_duration_seconds,
                max_chunk_gap_seconds=self._coalesce_max_gap_seconds,
            )
        except Exception as e:
            _logger.warning("Live pre-transcription VAD failed: %s", e)
            return None

    def _transcribe_missing(self, chunks: list[VadAudioChunk]) -> bool:
        for chunk in chunks:
            if self._transcript_for(chunk) is not None:
                continue
            transcript = self._transcribe_chunk(chunk)
            if transcript is None:
                return False
            with self._lock:
                self._transcripts[_chunk_key(chunk)] = transcript
        return True

    def _transcribe_chunk(self, chunk: VadAudioChunk) -> _ChunkTranscript | None:
        try:
            if self._client is None:
                self._client = self._client_factory(self._chunk_config)
            text = self._client.transcribe_audio(chunk.audio_data)
            if not text or not text.strip():
                _logger.warning("Live pre-transcription chunk returned no text")
                return None
            backend = getattr(self._client, "last_transcription_backend", None)
            return _ChunkTranscript(
                text=text,
                transcription_provider=getattr(backend, "provider", None),
                transcription_processor_id=getattr(backend, "processor_id", None),
            )
        except Exception as e:
            _logger.warning("Live pre-transcription chunk failed: %s", e)
            return None

    def _transcript_for(self, chunk: VadAudioChunk) -> _ChunkTranscript | None:
        with self._lock:
            return self._transcripts.get(_chunk_key(chunk))


def _chunk_key(chunk: VadAudioChunk) -> tuple[float, float]:
    return (round(chunk.segment.start_seconds, 3), round(chunk.segment.end_seconds, 3))
