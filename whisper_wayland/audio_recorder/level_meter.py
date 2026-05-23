"""Audio level analysis helpers for microphone calibration."""

from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import dataclass

TARGET_RMS_DBFS = -22.0
MIN_GOOD_RMS_DBFS = -30.0
MAX_GOOD_RMS_DBFS = -16.0
MAX_GOOD_PEAK_DBFS = -3.0
CLIP_WARNING_PERCENT = 0.1
INT16_MAX = 32768
INT16_CLIP_THRESHOLD = 32760
PCM16_SAMPLE_WIDTH_BYTES = 2
SILENT_RMS_DBFS = -90.0


@dataclass(frozen=True)
class AudioLevelStats:
    """Level summary for a mono/stereo PCM WAV sample."""

    duration_seconds: float
    sample_rate_hz: int
    channel_count: int
    rms_dbfs: float
    peak_dbfs: float
    clipping_percent: float
    verdict: str
    recommendation: str


def analyze_wav(audio_data: bytes) -> AudioLevelStats:
    """Analyze PCM16 WAV bytes for speech transcription suitability."""
    with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
        sample_width = wav_file.getsampwidth()
        channel_count = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        frame_count = wav_file.getnframes()
        frames = wav_file.readframes(frame_count)

    if sample_width != PCM16_SAMPLE_WIDTH_BYTES:
        raise ValueError(f"Expected 16-bit PCM WAV, got sample width {sample_width}")

    samples = _decode_int16_samples(frames)
    if channel_count > 1:
        samples = samples[::channel_count]

    duration = frame_count / sample_rate if sample_rate else 0.0
    if not samples:
        return AudioLevelStats(
            duration_seconds=duration,
            sample_rate_hz=sample_rate,
            channel_count=channel_count,
            rms_dbfs=-999.0,
            peak_dbfs=-999.0,
            clipping_percent=0.0,
            verdict="silent",
            recommendation="No audio samples found.",
        )

    peak = max(abs(sample) for sample in samples)
    rms = math.sqrt(sum(sample * sample for sample in samples) / len(samples))
    clipping_count = sum(1 for sample in samples if abs(sample) >= INT16_CLIP_THRESHOLD)
    clipping_percent = clipping_count / len(samples) * 100
    rms_dbfs = _dbfs(rms)
    peak_dbfs = _dbfs(peak)
    verdict, recommendation = _classify_levels(rms_dbfs, peak_dbfs, clipping_percent)

    return AudioLevelStats(
        duration_seconds=round(duration, 3),
        sample_rate_hz=sample_rate,
        channel_count=channel_count,
        rms_dbfs=round(rms_dbfs, 1),
        peak_dbfs=round(peak_dbfs, 1),
        clipping_percent=round(clipping_percent, 3),
        verdict=verdict,
        recommendation=recommendation,
    )


def recommended_volume_percent(stats: AudioLevelStats, current_percent: int) -> int:
    """Recommend next input volume percent from current level stats."""
    if stats.verdict == "too_hot":
        if stats.clipping_percent > CLIP_WARNING_PERCENT:
            ratio = 0.75
        else:
            ratio = 10 ** ((MAX_GOOD_PEAK_DBFS - stats.peak_dbfs) / 20)
        return _clamp_percent(round(current_percent * ratio))

    if stats.verdict == "too_quiet":
        ratio = 10 ** ((TARGET_RMS_DBFS - stats.rms_dbfs) / 20)
        ratio = min(ratio, 1.5)
        return _clamp_percent(round(current_percent * ratio))

    return _clamp_percent(current_percent)


def _decode_int16_samples(frames: bytes) -> tuple[int, ...]:
    sample_count = len(frames) // 2
    if sample_count == 0:
        return ()
    return struct.unpack(f"<{sample_count}h", frames[: sample_count * 2])


def _dbfs(value: float) -> float:
    if value <= 0:
        return -999.0
    return 20 * math.log10(value / INT16_MAX)


def _classify_levels(
    rms_dbfs: float,
    peak_dbfs: float,
    clipping_percent: float,
) -> tuple[str, str]:
    if rms_dbfs <= SILENT_RMS_DBFS:
        return "silent", "No usable speech detected. Check selected microphone."

    if clipping_percent > CLIP_WARNING_PERCENT or peak_dbfs > -1.0:
        return (
            "too_hot",
            "Input is clipping. Lower microphone volume or move the mic farther away.",
        )

    if rms_dbfs < MIN_GOOD_RMS_DBFS:
        return "too_quiet", "Input is quiet. Raise microphone volume or speak closer."

    if rms_dbfs > MAX_GOOD_RMS_DBFS or peak_dbfs > MAX_GOOD_PEAK_DBFS:
        return "loud", "Input is usable but hot. Lower volume slightly if quality sounds rough."

    return "ok", "Level looks good for transcription."


def _clamp_percent(value: int) -> int:
    return max(5, min(100, value))
