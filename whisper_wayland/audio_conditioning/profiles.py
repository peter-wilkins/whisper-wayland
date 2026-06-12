"""Profile settings for the Field Relay audio conditioning experiment."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ConditioningProfile:
    """Tunable FFmpeg/VAD settings for one acoustic profile."""

    name: str
    highpass_hz: int
    silence_threshold_db: int
    min_silence_duration_seconds: float
    min_speech_duration_seconds: float
    segment_padding_seconds: float
    join_gap_seconds: float
    opus_bitrate: str


DEFAULT_PROFILE_NAME = "clean"

PROFILES = {
    "clean": ConditioningProfile(
        name="clean",
        highpass_hz=80,
        silence_threshold_db=-38,
        min_silence_duration_seconds=0.35,
        min_speech_duration_seconds=0.35,
        segment_padding_seconds=0.12,
        join_gap_seconds=0.2,
        opus_bitrate="24k",
    ),
    "fanwind": ConditioningProfile(
        name="fanwind",
        highpass_hz=120,
        silence_threshold_db=-32,
        min_silence_duration_seconds=0.35,
        min_speech_duration_seconds=0.45,
        segment_padding_seconds=0.16,
        join_gap_seconds=0.25,
        opus_bitrate="24k",
    ),
    "fieldmovement": ConditioningProfile(
        name="fieldmovement",
        highpass_hz=140,
        silence_threshold_db=-30,
        min_silence_duration_seconds=0.3,
        min_speech_duration_seconds=0.45,
        segment_padding_seconds=0.2,
        join_gap_seconds=0.3,
        opus_bitrate="24k",
    ),
    "outdoorwind": ConditioningProfile(
        name="outdoorwind",
        highpass_hz=160,
        silence_threshold_db=-28,
        min_silence_duration_seconds=0.3,
        min_speech_duration_seconds=0.55,
        segment_padding_seconds=0.22,
        join_gap_seconds=0.35,
        opus_bitrate="24k",
    ),
    "nospeech": ConditioningProfile(
        name="nospeech",
        highpass_hz=140,
        silence_threshold_db=-30,
        min_silence_duration_seconds=0.25,
        min_speech_duration_seconds=0.7,
        segment_padding_seconds=0.05,
        join_gap_seconds=0.1,
        opus_bitrate="20k",
    ),
}


def profile_for_name(name: str) -> ConditioningProfile:
    """Return a named acoustic profile, falling back to clean."""
    return PROFILES.get(name, PROFILES[DEFAULT_PROFILE_NAME])

