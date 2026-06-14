"""Cheap local speech-likeness ranking for audio conditioning experiments."""

from __future__ import annotations

import math
import wave
from dataclasses import asdict, dataclass
from pathlib import Path

from whisper_wayland.audio_conditioning.models import SpeechSegment

SAMPLE_MAX = 32768.0
PCM_S16LE_SAMPLE_WIDTH = 2
MIN_ZERO_CROSSING_SAMPLES = 2
CLIPPING_SAMPLE_THRESHOLD = 32700
SILENT_RMS_THRESHOLD = 0.003
SILENT_PEAK_THRESHOLD = 0.01
SPEECH_CANDIDATE_SCORE_THRESHOLD = 0.45
CLIPPING_RATIO_THRESHOLD = 0.001
FRAME_SECONDS = 0.1


@dataclass(frozen=True)
class SpeechRanking:
    """Local score and features for one candidate speech segment."""

    score: float
    rms_amplitude: float
    peak_amplitude: float
    zero_crossing_rate: float
    rms_variation: float
    clipping_ratio: float
    duration_seconds: float
    reason: str

    def to_json(self) -> dict[str, float | str]:
        """Return JSON-friendly ranking payload."""
        return asdict(self)


def rank_speech_segment(wav_path: Path, segment: SpeechSegment) -> SpeechRanking:
    """Rank a segment using cheap PCM features, without transcription or network calls."""
    samples, sample_rate = _read_segment_samples(wav_path, segment)
    if not samples or sample_rate <= 0:
        return SpeechRanking(
            score=0.0,
            rms_amplitude=0.0,
            peak_amplitude=0.0,
            zero_crossing_rate=0.0,
            rms_variation=0.0,
            clipping_ratio=0.0,
            duration_seconds=segment.duration_seconds,
            reason="empty_segment",
        )

    rms = _rms_amplitude(samples)
    peak = max(abs(sample) for sample in samples) / SAMPLE_MAX
    zero_crossing_rate = _zero_crossing_rate(samples)
    rms_variation = _rms_variation(samples, sample_rate)
    clipping_ratio = sum(
        1 for sample in samples if abs(sample) >= CLIPPING_SAMPLE_THRESHOLD
    ) / len(samples)

    score, reason = _score_features(
        rms_amplitude=rms,
        peak_amplitude=peak,
        zero_crossing_rate=zero_crossing_rate,
        rms_variation=rms_variation,
        clipping_ratio=clipping_ratio,
        duration_seconds=segment.duration_seconds,
    )
    return SpeechRanking(
        score=score,
        rms_amplitude=round(rms, 6),
        peak_amplitude=round(peak, 6),
        zero_crossing_rate=round(zero_crossing_rate, 6),
        rms_variation=round(rms_variation, 6),
        clipping_ratio=round(clipping_ratio, 6),
        duration_seconds=segment.duration_seconds,
        reason=reason,
    )


def _read_segment_samples(wav_path: Path, segment: SpeechSegment) -> tuple[list[int], int]:
    with wave.open(str(wav_path), "rb") as wav_file:
        sample_width = wav_file.getsampwidth()
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        if sample_width != PCM_S16LE_SAMPLE_WIDTH:
            raise ValueError(f"Expected 16-bit PCM WAV, got sample width {sample_width}")

        start_frame = max(0, int(segment.start_seconds * sample_rate))
        frame_count = max(0, int(segment.duration_seconds * sample_rate))
        wav_file.setpos(min(start_frame, wav_file.getnframes()))
        raw = wav_file.readframes(frame_count)

    if channels <= 0:
        return [], sample_rate

    all_samples = [
        int.from_bytes(raw[index : index + 2], byteorder="little", signed=True)
        for index in range(0, len(raw), 2)
        if index + 2 <= len(raw)
    ]
    if channels == 1:
        return all_samples, sample_rate

    mono_samples = [
        int(sum(all_samples[index : index + channels]) / channels)
        for index in range(0, len(all_samples), channels)
        if len(all_samples[index : index + channels]) == channels
    ]
    return mono_samples, sample_rate


def _rms_amplitude(samples: list[int]) -> float:
    square_mean = sum(sample * sample for sample in samples) / len(samples)
    return math.sqrt(square_mean) / SAMPLE_MAX


def _zero_crossing_rate(samples: list[int]) -> float:
    if len(samples) < MIN_ZERO_CROSSING_SAMPLES:
        return 0.0

    crossings = 0
    previous = samples[0]
    for sample in samples[1:]:
        if (previous < 0 <= sample) or (previous >= 0 > sample):
            crossings += 1
        previous = sample
    return crossings / (len(samples) - 1)


def _rms_variation(samples: list[int], sample_rate: int) -> float:
    frame_size = max(1, int(sample_rate * FRAME_SECONDS))
    frame_rms_values = [
        _rms_amplitude(samples[index : index + frame_size])
        for index in range(0, len(samples), frame_size)
        if samples[index : index + frame_size]
    ]
    if len(frame_rms_values) < MIN_ZERO_CROSSING_SAMPLES:
        return 0.0

    mean_rms = sum(frame_rms_values) / len(frame_rms_values)
    if mean_rms <= 0:
        return 0.0
    variance = sum((value - mean_rms) ** 2 for value in frame_rms_values) / len(
        frame_rms_values
    )
    return min(2.0, math.sqrt(variance) / mean_rms)


def _score_features(  # noqa: PLR0913
    *,
    rms_amplitude: float,
    peak_amplitude: float,
    zero_crossing_rate: float,
    rms_variation: float,
    clipping_ratio: float,
    duration_seconds: float,
) -> tuple[float, str]:
    if rms_amplitude < SILENT_RMS_THRESHOLD or peak_amplitude < SILENT_PEAK_THRESHOLD:
        return 0.0, "likely_silent"

    loudness_score = _triangle_score(rms_amplitude, low=0.006, ideal=0.045, high=0.22)
    zcr_score = _triangle_score(zero_crossing_rate, low=0.015, ideal=0.07, high=0.22)
    duration_score = _triangle_score(duration_seconds, low=0.35, ideal=4.0, high=18.0)
    variation_score = _triangle_score(rms_variation, low=0.03, ideal=0.7, high=1.8)
    clipping_penalty = min(0.45, clipping_ratio * 20.0)

    score = (
        (0.3 * loudness_score)
        + (0.2 * zcr_score)
        + (0.1 * duration_score)
        + (0.4 * variation_score)
        - clipping_penalty
    )
    score = round(max(0.0, min(1.0, score)), 3)
    reason = (
        "speech_candidate"
        if score >= SPEECH_CANDIDATE_SCORE_THRESHOLD
        else "weak_speech_candidate"
    )
    if clipping_ratio > CLIPPING_RATIO_THRESHOLD:
        reason = f"{reason}_clipped"
    return score, reason


def _triangle_score(value: float, *, low: float, ideal: float, high: float) -> float:
    if value <= low or value >= high:
        return 0.0
    if value == ideal:
        return 1.0
    if value < ideal:
        return (value - low) / (ideal - low)
    return (high - value) / (high - ideal)
