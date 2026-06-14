"""Tests for Silero VAD preprocessing helpers."""

from __future__ import annotations

from whisper_wayland.silero_vad import _segments_from_probabilities

EXPECTED_SEGMENT_COUNT = 2
MIN_FIRST_SEGMENT_SECONDS = 0.5
MIN_SECOND_SEGMENT_SECONDS = 0.25


def test_segments_from_probabilities_groups_speech_regions() -> None:
    probabilities = [0.0] * 5 + [0.8] * 20 + [0.0] * 20 + [0.9] * 10

    segments = _segments_from_probabilities(
        probabilities,
        threshold=0.5,
        min_speech_seconds=0.2,
        min_silence_seconds=0.3,
        speech_pad_seconds=0.0,
    )

    assert len(segments) == EXPECTED_SEGMENT_COUNT
    assert segments[0].duration_seconds > MIN_FIRST_SEGMENT_SECONDS
    assert segments[1].duration_seconds > MIN_SECOND_SEGMENT_SECONDS
