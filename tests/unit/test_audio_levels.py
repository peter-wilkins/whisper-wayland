"""Audio level analysis tests."""

from __future__ import annotations

import io
import struct
import subprocess
import wave

from whisper_wayland.audio_recorder import microphone_calibrator
from whisper_wayland.audio_recorder.level_meter import (
    analyze_wav,
    recommended_volume_percent,
)
from whisper_wayland.audio_recorder.normalizer import normalize_wav_for_transcription

SAMPLE_RATE = 16000
DURATION_SECONDS = 1
QUIET_RMS_THRESHOLD = -30
TARGET_RMS_DBFS = -22
MAX_PEAK_AMPLITUDE = 0.95
MAX_GAIN = 6
QUIET_SAMPLE = 120
GOOD_SAMPLE = 2400
CLIPPED_SAMPLE = 32767
FULL_CLIPPING_PERCENT = 100
CURRENT_VOLUME = 40
PACTL_VOLUME_PERCENT = 27


def _wav_with_sample(sample: int) -> bytes:
    frame_count = SAMPLE_RATE * DURATION_SECONDS
    payload = struct.pack(f"<{frame_count}h", *([sample] * frame_count))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(payload)
    return buffer.getvalue()


def test_analyze_wav_detects_quiet_audio() -> None:
    """Quiet audio gets a raise-volume recommendation."""
    stats = analyze_wav(_wav_with_sample(QUIET_SAMPLE))

    assert stats.verdict == "too_quiet"
    assert stats.sample_rate_hz == SAMPLE_RATE
    assert stats.duration_seconds == DURATION_SECONDS
    assert stats.rms_dbfs < QUIET_RMS_THRESHOLD
    assert recommended_volume_percent(stats, CURRENT_VOLUME) > CURRENT_VOLUME


def test_analyze_wav_accepts_good_speech_level() -> None:
    """Speech-level audio is OK."""
    stats = analyze_wav(_wav_with_sample(GOOD_SAMPLE))

    assert stats.verdict == "ok"
    assert stats.clipping_percent == 0
    assert recommended_volume_percent(stats, CURRENT_VOLUME) == CURRENT_VOLUME


def test_analyze_wav_detects_clipping() -> None:
    """Clipped audio gets a lower-volume recommendation."""
    stats = analyze_wav(_wav_with_sample(CLIPPED_SAMPLE))

    assert stats.verdict == "too_hot"
    assert stats.clipping_percent == FULL_CLIPPING_PERCENT
    assert recommended_volume_percent(stats, CURRENT_VOLUME) < CURRENT_VOLUME


def test_normalizer_amplifies_quiet_audio_for_transcription() -> None:
    """Transcription-only normalization raises quiet WAV levels."""
    audio_data = _wav_with_sample(QUIET_SAMPLE)
    before = analyze_wav(audio_data)

    result = normalize_wav_for_transcription(
        audio_data,
        target_rms_dbfs=TARGET_RMS_DBFS,
        max_peak_amplitude=MAX_PEAK_AMPLITUDE,
        max_gain=MAX_GAIN,
    )
    after = analyze_wav(result.audio_data)

    assert result.applied
    assert result.gain > 1
    assert after.rms_dbfs > before.rms_dbfs
    assert after.peak_amplitude <= MAX_PEAK_AMPLITUDE


def test_normalizer_does_not_boost_clipped_audio() -> None:
    """Normalization does not amplify audio already at peak."""
    audio_data = _wav_with_sample(CLIPPED_SAMPLE)

    result = normalize_wav_for_transcription(
        audio_data,
        target_rms_dbfs=TARGET_RMS_DBFS,
        max_peak_amplitude=MAX_PEAK_AMPLITUDE,
        max_gain=MAX_GAIN,
    )

    assert not result.applied
    assert result.audio_data == audio_data


def test_get_source_volume_percent_parses_pactl(monkeypatch) -> None:
    """Parse pactl source volume output."""

    def fake_run_pactl(args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args,
            returncode=0,
            stdout=(
                f"Volume: front-left: 17990 /  {PACTL_VOLUME_PERCENT}% / -33.69 dB, "
                f"front-right: 17990 /  {PACTL_VOLUME_PERCENT}% / -33.69 dB\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(microphone_calibrator, "_run_pactl", fake_run_pactl)

    assert (
        microphone_calibrator.get_source_volume_percent("@DEFAULT_SOURCE@")
        == PACTL_VOLUME_PERCENT
    )


def test_set_source_volume_percent_uses_pactl(monkeypatch) -> None:
    """Set source volume through pactl."""
    calls = []

    def fake_run_pactl(args: list[str]) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr(microphone_calibrator, "_run_pactl", fake_run_pactl)

    assert microphone_calibrator.set_source_volume_percent("@DEFAULT_SOURCE@", 32)
    assert calls == [["set-source-volume", "@DEFAULT_SOURCE@", "32%"]]
