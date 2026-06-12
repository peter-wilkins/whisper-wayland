"""FFmpeg helpers for local audio conditioning experiments."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from whisper_wayland.audio_conditioning.models import SpeechSegment
from whisper_wayland.audio_conditioning.profiles import ConditioningProfile

SILENCE_START_RE = re.compile(r"silence_start: (?P<seconds>[0-9.]+)")
SILENCE_END_RE = re.compile(r"silence_end: (?P<seconds>[0-9.]+)")


class FFmpegError(Exception):
    """Raised when FFmpeg/ffprobe work fails."""


def probe_duration_seconds(path: Path) -> float:
    """Return media duration via ffprobe."""
    result = _run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    payload = json.loads(result.stdout)
    return round(float(payload["format"]["duration"]), 3)


def highpass_to_wav(source_path: Path, output_path: Path, profile: ConditioningProfile) -> None:
    """Apply a portable high-pass filter and normalize format to mono PCM WAV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(source_path),
            "-af",
            f"highpass=f={profile.highpass_hz}",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-c:a",
            "pcm_s16le",
            str(output_path),
        ]
    )


def detect_speech_segments(
    wav_path: Path,
    duration_seconds: float,
    profile: ConditioningProfile,
) -> list[SpeechSegment]:
    """Detect speech-like regions as the inverse of FFmpeg silencedetect output."""
    result = _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-i",
            str(wav_path),
            "-af",
            (
                "silencedetect="
                f"noise={profile.silence_threshold_db}dB:"
                f"d={profile.min_silence_duration_seconds}"
            ),
            "-f",
            "null",
            "-",
        ],
        allow_stderr=True,
    )
    silence_ranges = _parse_silence_ranges(result.stderr, duration_seconds)
    raw_segments = _speech_from_silence_ranges(silence_ranges, duration_seconds)
    padded = _pad_and_join_segments(raw_segments, duration_seconds, profile)
    return [
        SpeechSegment(index=index, start_seconds=start, end_seconds=end)
        for index, (start, end) in enumerate(padded, start=1)
        if end - start >= profile.min_speech_duration_seconds
    ]


def export_opus_segment(
    wav_path: Path,
    output_path: Path,
    segment: SpeechSegment,
    profile: ConditioningProfile,
) -> None:
    """Export one detected speech segment as Opus."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-ss",
            f"{segment.start_seconds:.3f}",
            "-t",
            f"{segment.duration_seconds:.3f}",
            "-i",
            str(wav_path),
            "-c:a",
            "libopus",
            "-b:a",
            profile.opus_bitrate,
            "-vbr",
            "on",
            str(output_path),
        ]
    )


def _parse_silence_ranges(stderr: str, duration_seconds: float) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    current_start: float | None = None
    for line in stderr.splitlines():
        start_match = SILENCE_START_RE.search(line)
        if start_match:
            current_start = float(start_match.group("seconds"))
            continue

        end_match = SILENCE_END_RE.search(line)
        if end_match and current_start is not None:
            ranges.append((current_start, float(end_match.group("seconds"))))
            current_start = None

    if current_start is not None:
        ranges.append((current_start, duration_seconds))

    return [(max(0.0, start), min(duration_seconds, end)) for start, end in ranges]


def _speech_from_silence_ranges(
    silence_ranges: list[tuple[float, float]],
    duration_seconds: float,
) -> list[tuple[float, float]]:
    if not silence_ranges:
        return [(0.0, duration_seconds)] if duration_seconds > 0 else []

    segments: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in silence_ranges:
        if start > cursor:
            segments.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < duration_seconds:
        segments.append((cursor, duration_seconds))
    return segments


def _pad_and_join_segments(
    segments: list[tuple[float, float]],
    duration_seconds: float,
    profile: ConditioningProfile,
) -> list[tuple[float, float]]:
    padded = [
        (
            round(max(0.0, start - profile.segment_padding_seconds), 3),
            round(min(duration_seconds, end + profile.segment_padding_seconds), 3),
        )
        for start, end in segments
    ]
    if not padded:
        return []

    joined = [padded[0]]
    for start, end in padded[1:]:
        previous_start, previous_end = joined[-1]
        if start - previous_end <= profile.join_gap_seconds:
            joined[-1] = (previous_start, max(previous_end, end))
        else:
            joined.append((start, end))
    return joined


def _run(
    args: list[str],
    *,
    allow_stderr: bool = False,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(  # noqa: S603 - fixed executable args, no shell
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FFmpegError(result.stderr.strip() or result.stdout.strip())
    if not allow_stderr and result.stderr:
        return result
    return result

