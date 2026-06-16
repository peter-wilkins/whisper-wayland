"""Tests for Silero VAD preprocessing helpers."""

from __future__ import annotations

from whisper_wayland.silero_vad import VadSegment, _coalesce_segments, _segments_from_probabilities

EXPECTED_SEGMENT_COUNT = 2
EXPECTED_COALESCED_SEGMENT_COUNT = 2
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


def test_coalesce_segments_merges_tiny_adjacent_speech_regions() -> None:
    segments = [
        VadSegment(start_seconds=0.0, end_seconds=3.0),
        VadSegment(start_seconds=5.0, end_seconds=5.8),
        VadSegment(start_seconds=6.1, end_seconds=8.0),
        VadSegment(start_seconds=20.0, end_seconds=23.0),
    ]

    coalesced = _coalesce_segments(
        segments,
        min_chunk_duration_seconds=4.0,
        max_chunk_duration_seconds=12.0,
        max_chunk_gap_seconds=3.0,
    )

    assert len(coalesced) == EXPECTED_COALESCED_SEGMENT_COUNT
    assert coalesced[0] == VadSegment(start_seconds=0.0, end_seconds=8.0)
    assert coalesced[1] == VadSegment(start_seconds=20.0, end_seconds=23.0)
