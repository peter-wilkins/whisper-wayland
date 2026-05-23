"""WAV normalization for transcription-only audio."""

from __future__ import annotations

import io
import struct
import wave
from dataclasses import dataclass

from whisper_wayland.audio_recorder.level_meter import (
    PCM16_SAMPLE_WIDTH_BYTES,
    analyze_wav,
)

INT16_MIN_VALUE = -32768
INT16_MAX_VALUE = 32767
MIN_USEFUL_GAIN = 1.001


@dataclass(frozen=True)
class NormalizationResult:
    """Result of transcription-only audio normalization."""

    audio_data: bytes
    applied: bool
    gain: float
    before_rms_dbfs: float
    after_rms_dbfs: float
    before_peak_dbfs: float
    after_peak_dbfs: float


def normalize_wav_for_transcription(
    audio_data: bytes,
    target_rms_dbfs: float,
    max_peak_amplitude: float,
    max_gain: float,
) -> NormalizationResult:
    """Normalize PCM16 WAV bytes for transcription without mutating capture audio."""
    before = analyze_wav(audio_data)
    if before.peak_amplitude <= 0 or before.rms_amplitude <= 0:
        return _unchanged(audio_data, before.rms_dbfs, before.peak_dbfs)

    target_rms_amplitude = 10 ** (target_rms_dbfs / 20)
    rms_gain = target_rms_amplitude / before.rms_amplitude
    peak_gain = max_peak_amplitude / before.peak_amplitude
    gain = max(1.0, min(rms_gain, peak_gain, max_gain))

    if gain <= MIN_USEFUL_GAIN:
        return _unchanged(audio_data, before.rms_dbfs, before.peak_dbfs)

    normalized_audio = _apply_gain_to_pcm16_wav(audio_data, gain)
    after = analyze_wav(normalized_audio)
    return NormalizationResult(
        audio_data=normalized_audio,
        applied=True,
        gain=round(gain, 3),
        before_rms_dbfs=before.rms_dbfs,
        after_rms_dbfs=after.rms_dbfs,
        before_peak_dbfs=before.peak_dbfs,
        after_peak_dbfs=after.peak_dbfs,
    )


def _unchanged(audio_data: bytes, rms_dbfs: float, peak_dbfs: float) -> NormalizationResult:
    return NormalizationResult(
        audio_data=audio_data,
        applied=False,
        gain=1.0,
        before_rms_dbfs=rms_dbfs,
        after_rms_dbfs=rms_dbfs,
        before_peak_dbfs=peak_dbfs,
        after_peak_dbfs=peak_dbfs,
    )


def _apply_gain_to_pcm16_wav(audio_data: bytes, gain: float) -> bytes:
    input_buffer = io.BytesIO(audio_data)
    output_buffer = io.BytesIO()

    with wave.open(input_buffer, "rb") as input_wav:
        params = input_wav.getparams()
        if input_wav.getsampwidth() != PCM16_SAMPLE_WIDTH_BYTES:
            raise ValueError(
                f"Expected 16-bit PCM WAV, got sample width {input_wav.getsampwidth()}"
            )

        frames = input_wav.readframes(input_wav.getnframes())
        samples = struct.unpack(f"<{len(frames) // 2}h", frames)
        adjusted = [_clamp_int16(round(sample * gain)) for sample in samples]
        adjusted_frames = struct.pack(f"<{len(adjusted)}h", *adjusted)

    with wave.open(output_buffer, "wb") as output_wav:
        output_wav.setparams(params)
        output_wav.writeframes(adjusted_frames)

    return output_buffer.getvalue()


def _clamp_int16(value: int) -> int:
    return max(INT16_MIN_VALUE, min(INT16_MAX_VALUE, value))
