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

from whisper_wayland.audio_recorder.level_meter import analyze_wav
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
    event_paths: tuple[Path, ...]


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
    transcript_suppressed: bool
    transcript_suppression_reason: str | None
    capture_id: str
    created_at_text: str
    artifact_rel: Path
    event_rels: tuple[Path, ...]


class CaptureTap:
    """Opt-in local file-drop capture tap for Continuum."""

    SCHEMA_VERSION = "continuum.audio-capture-tap.v1"
    LOCAL_EVENT_SCHEMA_VERSION = "whisper-wayland.continuum-audio-local-event.v1"
    AUDIO_LAYER_NAME = "Continuum Audio"
    EVENT_NAMESPACE = "continuum.audio"
    INTENTIONAL_CAPTURE_EVENT_NAME = "intentional_capture.v1"
    AUDIO_SEGMENT_EVENT_NAME = "audio_segment.v1"
    CAPTURE_HEALTH_EVENT_NAME = "capture_health.v1"
    TRANSCRIPT_FEEDBACK_EVENT_NAME = "transcript_feedback.v1"
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
        *,
        transcript_suppressed: bool = False,
        transcript_suppression_reason: str | None = None,
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
            event_rels = self._event_relative_paths(
                created_at=created_at,
                filename_stem=filename_stem,
                transcript_suppressed=transcript_suppressed,
            )
            artifact_path = self._inlet_dir / artifact_rel
            envelope_path = self._inlet_dir / envelope_rel
            event_paths = tuple(self._inlet_dir / event_rel for event_rel in event_rels)

            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            envelope_path.parent.mkdir(parents=True, exist_ok=True)
            for event_path in event_paths:
                event_path.parent.mkdir(parents=True, exist_ok=True)

            artifact_path.write_bytes(audio_data)
            envelope = self._build_envelope(
                CaptureEnvelopeInput(
                    audio_data=audio_data,
                    raw_transcript_text=raw_transcript_text,
                    insertion_text=insertion_text,
                    transcript_suppressed=transcript_suppressed,
                    transcript_suppression_reason=transcript_suppression_reason,
                    capture_id=capture_id,
                    created_at_text=created_at_text,
                    artifact_rel=artifact_rel,
                    event_rels=event_rels,
                )
            )
            events = self._build_local_events(envelope)
            for event_path, event in zip(event_paths, events, strict=True):
                self._write_json_atomically(event_path, event)
            self._write_envelope_atomically(envelope_path, envelope)

            _logger.info("Continuum capture tap wrote envelope: %s", envelope_path)
            return CaptureTapWriteResult(
                capture_id=capture_id,
                artifact_path=artifact_path,
                envelope_path=envelope_path,
                event_paths=event_paths,
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
        capture_health = self._build_capture_health(audio_data, wav_metadata)
        transcript = self._build_transcript(envelope_input)
        event_names = self._event_names_for_capture(envelope_input.transcript_suppressed)

        return {
            "schemaVersion": self.SCHEMA_VERSION,
            "captureId": envelope_input.capture_id,
            "continuumAudio": {
                "layerName": self.AUDIO_LAYER_NAME,
                "eventNamespace": self.EVENT_NAMESPACE,
                "sourceConcept": "intentional capture",
                "artifactConcept": "audio segment",
                "eventNames": event_names,
                "stability": "concepts_and_event_names_only",
            },
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
            "audioSegments": [
                {
                    "segmentId": f"{envelope_input.capture_id}:segment:0001",
                    "eventName": self.AUDIO_SEGMENT_EVENT_NAME,
                    "kind": "full_intentional_capture",
                    "relativePath": envelope_input.artifact_rel.as_posix(),
                    "startOffsetSeconds": 0,
                    "durationSeconds": wav_metadata.duration_seconds,
                    "provenance": "batch_capture_artifact",
                }
            ],
            "captureHealth": capture_health,
            "transcript": transcript,
            "captureContext": {
                "hostApp": self.SOURCE_TOOL_NAME,
                "captureInlet": "local-file-drop",
                "intentionalCapture": True,
                "deviceLabel": self._device_label(),
                "membraneDecision": (
                    "needs_review" if envelope_input.transcript_suppressed else "accepted"
                ),
                "contextClues": [
                    {
                        "kind": "activation",
                        "text": "push-to-talk hotkey released",
                        "confidence": 1,
                        "observedAt": envelope_input.created_at_text,
                    }
                ],
            },
            "localEventArtifacts": [
                {
                    "eventName": event_name,
                    "relativePath": event_rel.as_posix(),
                }
                for event_name, event_rel in zip(event_names[1:], envelope_input.event_rels)
            ],
            "processor": {
                "provider": "openai",
                "processorId": processor_id,
                "processorVersion": "unknown",
                "processorKind": "transcription",
                "configurationFingerprint": self._configuration_fingerprint(processor_id),
                "knowledgeTime": envelope_input.created_at_text,
            },
        }

    def _build_local_events(
        self,
        envelope: dict[str, typing.Any],
    ) -> tuple[dict[str, typing.Any], ...]:
        """Build local sidecar event artifacts using stable Continuum Audio event names."""
        base_event = {
            "schemaVersion": self.LOCAL_EVENT_SCHEMA_VERSION,
            "eventNamespace": self.EVENT_NAMESPACE,
            "captureId": envelope["captureId"],
            "createdAt": envelope["captureTap"]["createdAt"],
            "sourceTool": envelope["sourceTool"],
        }
        health_event = {
            **base_event,
            "eventName": self.CAPTURE_HEALTH_EVENT_NAME,
            "localPayload": {
                "captureHealth": envelope["captureHealth"],
                "audioArtifact": envelope["audioArtifact"],
            },
        }
        if envelope["captureContext"]["membraneDecision"] != "needs_review":
            return (health_event,)

        transcript = envelope["transcript"]
        feedback_event = {
            **base_event,
            "eventName": self.TRANSCRIPT_FEEDBACK_EVENT_NAME,
            "localPayload": {
                "feedbackKind": "transcript_rejected",
                "membraneDecision": "needs_review",
                "suppressionReason": transcript.get("suppressionReason"),
                "rejectedRawTranscriptText": transcript.get("rejectedRawTranscriptText", ""),
                "rejectedInsertionText": transcript.get("rejectedInsertionText", ""),
                "postProcessMode": transcript["postProcessMode"],
            },
        }
        return (health_event, feedback_event)

    def _build_transcript(
        self,
        envelope_input: CaptureEnvelopeInput,
    ) -> dict[str, typing.Any]:
        """Build transcript section, making suppressed hallucinations explicit."""
        transcript = {
            "rawTranscriptText": envelope_input.raw_transcript_text,
            "insertionText": envelope_input.insertion_text,
            "postProcessMode": self._config.text_post_process_mode,
        }

        if not envelope_input.transcript_suppressed:
            return transcript

        return {
            "rawTranscriptText": "",
            "insertionText": "",
            "postProcessMode": self._config.text_post_process_mode,
            "suppressed": True,
            "suppressionReason": envelope_input.transcript_suppression_reason,
            "rejectedRawTranscriptText": envelope_input.raw_transcript_text,
            "rejectedInsertionText": envelope_input.insertion_text,
        }

    def _build_capture_health(
        self,
        audio_data: bytes,
        wav_metadata: WavMetadata,
    ) -> dict[str, typing.Any]:
        """Build cheap capture-health evidence from local WAV bytes."""
        try:
            stats = analyze_wav(audio_data)
            likely_silent = stats.likely_silent
            likely_clipped = stats.likely_clipped
            rms_amplitude = stats.rms_amplitude
            peak_amplitude = stats.peak_amplitude
            clipping_ratio = stats.clipping_ratio
        except Exception as e:
            _logger.warning("Could not compute capture health: %s", e)
            likely_silent = False
            likely_clipped = False
            rms_amplitude = 0.0
            peak_amplitude = 0.0
            clipping_ratio = 0.0

        return {
            "durationSeconds": wav_metadata.duration_seconds,
            "byteLength": len(audio_data),
            "rmsAmplitude": rms_amplitude,
            "peakAmplitude": peak_amplitude,
            "clippingRatio": clipping_ratio,
            "likelySilent": likely_silent,
            "likelyClipped": likely_clipped,
            "checks": self._build_capture_health_checks(
                likely_silent=likely_silent,
                likely_clipped=likely_clipped,
            ),
        }

    @staticmethod
    def _build_capture_health_checks(
        likely_silent: bool,
        likely_clipped: bool,
    ) -> list[dict[str, typing.Any]]:
        """Build human-readable capture health checks for Continuum."""
        return [
            {
                "kind": "rms_level",
                "status": "fail" if likely_silent else "pass",
                "text": (
                    "RMS or peak amplitude is below the likely-silent threshold."
                    if likely_silent
                    else "RMS and peak amplitude are above the likely-silent thresholds."
                ),
                "confidence": 1,
            },
            {
                "kind": "clipping",
                "status": "fail" if likely_clipped else "pass",
                "text": (
                    "Clipping ratio is above the likely-clipped threshold."
                    if likely_clipped
                    else "Clipping ratio is below the likely-clipped threshold."
                ),
                "confidence": 1,
            },
        ]

    @staticmethod
    def _write_envelope_atomically(envelope_path: Path, envelope: dict[str, typing.Any]) -> None:
        """Write envelope via tmp file then atomic rename."""
        CaptureTap._write_json_atomically(envelope_path, envelope)

    @staticmethod
    def _write_json_atomically(path: Path, payload: dict[str, typing.Any]) -> None:
        """Write JSON via tmp file then atomic rename."""
        tmp_path = Path(f"{path}.tmp")
        text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
        tmp_path.write_text(text, encoding="utf-8")
        tmp_path.replace(path)

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

    @classmethod
    def _event_names_for_capture(cls, transcript_suppressed: bool) -> list[str]:
        event_names = [
            cls.INTENTIONAL_CAPTURE_EVENT_NAME,
            cls.CAPTURE_HEALTH_EVENT_NAME,
        ]
        if transcript_suppressed:
            event_names.append(cls.TRANSCRIPT_FEEDBACK_EVENT_NAME)
        return event_names

    @classmethod
    def _event_relative_paths(
        cls,
        *,
        created_at: datetime,
        filename_stem: str,
        transcript_suppressed: bool,
    ) -> tuple[Path, ...]:
        event_dir = Path("events") / created_at.date().isoformat()
        event_rels = [
            event_dir / f"{filename_stem}-{cls.CAPTURE_HEALTH_EVENT_NAME}.json",
        ]
        if transcript_suppressed:
            event_rels.append(
                event_dir / f"{filename_stem}-{cls.TRANSCRIPT_FEEDBACK_EVENT_NAME}.json"
            )
        return tuple(event_rels)

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
