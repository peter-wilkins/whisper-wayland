"""Data models for the audio conditioning harness."""

from __future__ import annotations

import typing
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SpeechSegment:
    """A speech-like interval detected in a source audio file."""

    index: int
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        """Segment duration in seconds."""
        return round(max(0.0, self.end_seconds - self.start_seconds), 3)


@dataclass(frozen=True)
class Fixture:
    """One local-only audio fixture and sidecar metadata."""

    fixture_id: str
    source_path: Path
    acoustic_profile: str
    scenario: str
    expected_words: list[str]
    expected_silence: bool
    expected_speech_windows: list[dict[str, float]]
    noise_notes: str
    notes: str


@dataclass(frozen=True)
class SegmentArtifact:
    """An exported Opus segment file."""

    segment: SpeechSegment
    path: Path
    byte_length: int


@dataclass(frozen=True)
class TranscriptionResult:
    """Optional transcription comparison output."""

    original_text: str | None
    conditioned_text: str | None
    error: str | None


@dataclass(frozen=True)
class FixtureResult:
    """Harness result for one fixture."""

    fixture: Fixture
    profile: dict[str, typing.Any]
    original_duration_seconds: float
    original_byte_length: int
    conditioned_wav_byte_length: int
    kept_duration_seconds: float
    discarded_duration_seconds: float
    opus_byte_length: int
    upload_size_reduction_percent: float
    detected_segments: list[SpeechSegment]
    segment_artifacts: list[SegmentArtifact]
    transcription: TranscriptionResult | None
    passed: bool
    failure_reasons: list[str]

