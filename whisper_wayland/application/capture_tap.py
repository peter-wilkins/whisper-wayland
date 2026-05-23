"""Continuum audio capture tap.

Writes opt-in local file-drop capture artifacts for Continuum.
"""

from __future__ import annotations

import hashlib
import io
import itertools
import json
import logging
import os
import threading
import typing
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from whisper_wayland.transcription_client.model_mapper import ModelMapper

_logger = logging.getLogger(__name__)

_CAPTURE_COUNTER = itertools.count(1)
_CAPTURE_COUNTER_LOCK = threading.Lock()


@dataclass(frozen=True)
class CaptureTapWriteResult:
    """Paths written by a capture tap commit."""

    capture_id: str
    artifact_path: Path
    envelope_path: Path


@dataclass(frozen=True)
class WavMetadata:
    """Small WAV metadata subset needed by the Continuum envelope."""

    sample_rate_hz: int
    channel_count: int
    duration_seconds: float


@dataclass(frozen=True)
class CaptureEnvelopeInput:
    """Values needed to build a Continuum envelope."""

    audio_data: bytes
    raw_transcript_text: str
    insertion_text: str
    capture_id: str
    created_at_text: str
    artifact_rel: Path


class CaptureTap:
    """Opt-in local file-drop capture tap for Continuum."""

    SCHEMA_VERSION = "continuum.audio-capture-tap.v1"
    SOURCE_TOOL_NAME = "whisper-wayland"
    TAP_POINT = "after_batch_transcription_before_text_insertion"

    def __init__(
        self,
        config: typing.Any,
        clock: typing.Callable[[], datetime] | None = None,
    ) -> None:
        """Initialize capture tap from config."""
        self._config = config
        inlet_dir = getattr(config, "continuum_capture_inlet_dir", "")
        if not isinstance(inlet_dir, (str, os.PathLike)):
            inlet_dir = ""
        self._inlet_dir = Path(inlet_dir).expanduser() if inlet_dir else None
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._model_mapper = ModelMapper.new()

    @property
    def enabled(self) -> bool:
        """Return whether local capture file-drop is enabled."""
        return self._inlet_dir is not None

    def write(
        self,
        audio_data: bytes,
        raw_transcript_text: str,
        insertion_text: str,
    ) -> CaptureTapWriteResult | None:
        """Write local WAV artifact and JSON envelope if capture tap is enabled."""
        if not self._inlet_dir:
            return None

        try:
            created_at = self._clock()
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            created_at = created_at.astimezone(timezone.utc)

            counter = self._next_counter()
            timestamp_for_id = self._format_timestamp_for_id(created_at)
            created_at_text = self._format_created_at(created_at)
            pid = os.getpid()
            capture_id = f"{self.SOURCE_TOOL_NAME}:{timestamp_for_id}:{pid}:{counter:04d}"
            filename_stem = f"{self.SOURCE_TOOL_NAME}-{timestamp_for_id}-{pid}-{counter:04d}"

            artifact_rel = (
                Path("artifacts") / created_at.date().isoformat() / f"{filename_stem}.wav"
            )
            envelope_rel = Path("envelopes") / f"{filename_stem}.json"
            artifact_path = self._inlet_dir / artifact_rel
            envelope_path = self._inlet_dir / envelope_rel

            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            envelope_path.parent.mkdir(parents=True, exist_ok=True)

            artifact_path.write_bytes(audio_data)
            envelope = self._build_envelope(
                CaptureEnvelopeInput(
                    audio_data=audio_data,
                    raw_transcript_text=raw_transcript_text,
                    insertion_text=insertion_text,
                    capture_id=capture_id,
                    created_at_text=created_at_text,
                    artifact_rel=artifact_rel,
                )
            )
            self._write_envelope_atomically(envelope_path, envelope)

            _logger.info("Continuum capture tap wrote envelope: %s", envelope_path)
            return CaptureTapWriteResult(
                capture_id=capture_id,
                artifact_path=artifact_path,
                envelope_path=envelope_path,
            )
        except Exception as e:
            _logger.error("Continuum capture tap write failed: %s", e)
            return None

    def _build_envelope(self, envelope_input: CaptureEnvelopeInput) -> dict[str, typing.Any]:
        """Build Continuum capture envelope."""
        audio_data = envelope_input.audio_data
        wav_metadata = self._read_wav_metadata(audio_data)
        artifact_hash = hashlib.sha256(audio_data).hexdigest()
        processor_id = self._model_mapper.map_model_name(self._config.whisper_model)

        return {
            "schemaVersion": self.SCHEMA_VERSION,
            "captureId": envelope_input.capture_id,
            "sourceTool": {
                "name": self.SOURCE_TOOL_NAME,
                "version": self._source_tool_version(),
                "repoPath": str(self._repo_path()),
            },
            "captureTap": {
                "point": self.TAP_POINT,
                "createdAt": envelope_input.created_at_text,
            },
            "audioArtifact": {
                "relativePath": envelope_input.artifact_rel.as_posix(),
                "mimeType": "audio/wav",
                "codec": "pcm_s16le",
                "sampleRateHz": wav_metadata.sample_rate_hz,
                "channelCount": wav_metadata.channel_count,
                "durationSeconds": wav_metadata.duration_seconds,
                "byteLength": len(audio_data),
                "sha256": artifact_hash,
            },
            "transcript": {
                "rawTranscriptText": envelope_input.raw_transcript_text,
                "insertionText": envelope_input.insertion_text,
                "postProcessMode": self._config.text_post_process_mode,
            },
            "captureContext": {
                "hostApp": self.SOURCE_TOOL_NAME,
                "captureInlet": "local-file-drop",
                "deviceLabel": self._device_label(),
                "membraneDecision": "accepted",
                "contextClues": [
                    {
                        "kind": "activation",
                        "text": "push-to-talk hotkey released",
                        "confidence": 1,
                        "observedAt": envelope_input.created_at_text,
                    }
                ],
            },
            "processor": {
                "provider": "openai",
                "processorId": processor_id,
                "processorVersion": "unknown",
                "processorKind": "transcription",
                "configurationFingerprint": self._configuration_fingerprint(processor_id),
                "knowledgeTime": envelope_input.created_at_text,
            },
        }

    @staticmethod
    def _write_envelope_atomically(envelope_path: Path, envelope: dict[str, typing.Any]) -> None:
        """Write envelope via tmp file then atomic rename."""
        tmp_path = Path(f"{envelope_path}.tmp")
        payload = json.dumps(envelope, indent=2, sort_keys=True) + "\n"
        tmp_path.write_text(payload, encoding="utf-8")
        tmp_path.replace(envelope_path)

    def _read_wav_metadata(self, audio_data: bytes) -> WavMetadata:
        """Read basic WAV metadata, falling back to config if parsing fails."""
        try:
            with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
                sample_rate = wav_file.getframerate()
                channels = wav_file.getnchannels()
                frames = wav_file.getnframes()
                duration = frames / sample_rate if sample_rate else 0.0
                return WavMetadata(
                    sample_rate_hz=sample_rate,
                    channel_count=channels,
                    duration_seconds=round(duration, 6),
                )
        except Exception as e:
            _logger.warning("Could not read WAV metadata for capture tap: %s", e)
            return WavMetadata(
                sample_rate_hz=self._config.audio_sample_rate,
                channel_count=1,
                duration_seconds=0.0,
            )

    def _configuration_fingerprint(self, processor_id: str) -> str:
        """Build stable non-secret fingerprint of transcription config."""
        config_subset = {
            "audio_sample_rate": self._config.audio_sample_rate,
            "processor_id": processor_id,
            "text_post_process_mode": self._config.text_post_process_mode,
            "text_post_process_model": self._config.text_post_process_model,
            "whisper_model": self._config.whisper_model,
        }
        payload = json.dumps(config_subset, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

    def _device_label(self) -> str:
        """Return best available non-secret audio device label."""
        if self._config.audio_input_device_name:
            return self._config.audio_input_device_name
        if self._config.audio_input_device_index is not None:
            return f"input device index {self._config.audio_input_device_index}"
        return "system default microphone"

    @staticmethod
    def _next_counter() -> int:
        with _CAPTURE_COUNTER_LOCK:
            return next(_CAPTURE_COUNTER)

    @staticmethod
    def _format_timestamp_for_id(created_at: datetime) -> str:
        return f"{created_at:%Y%m%dT%H%M%S}{created_at.microsecond // 1000:03d}Z"

    @staticmethod
    def _format_created_at(created_at: datetime) -> str:
        return created_at.isoformat(timespec="milliseconds").replace("+00:00", "Z")

    @staticmethod
    def _repo_path() -> Path:
        return Path(__file__).resolve().parents[2]

    @staticmethod
    def _source_tool_version() -> str:
        try:
            return metadata.version("whisper-wayland")
        except metadata.PackageNotFoundError:
            return "unknown"
