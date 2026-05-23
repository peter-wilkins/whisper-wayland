"""Audio level monitor tests."""

from __future__ import annotations

import io
import struct
import types
import unittest.mock
import wave

from whisper_wayland.application.audio_level_monitor import AudioLevelMonitor

SAMPLE_RATE = 16000
DURATION_SECONDS = 1
CLIPPED_SAMPLE = 32767
CURRENT_VOLUME = 27
EXPECTED_REDUCED_VOLUME = 20
CHECK_INTERVAL_SECS = 60


def _clipped_wav() -> bytes:
    frame_count = SAMPLE_RATE * DURATION_SECONDS
    payload = struct.pack(f"<{frame_count}h", *([CLIPPED_SAMPLE] * frame_count))
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(payload)
    return buffer.getvalue()


def _config(auto_adjust: bool = True) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        audio_level_monitor_enabled=True,
        audio_level_auto_adjust_enabled=auto_adjust,
        audio_level_manage_mics_enabled=auto_adjust,
        audio_level_check_interval_secs=CHECK_INTERVAL_SECS,
        audio_level_source="@DEFAULT_SOURCE@",
    )


def test_audio_level_monitor_auto_adjusts_clipped_audio(monkeypatch) -> None:
    """Monitor lowers source volume when captured audio clips."""
    set_calls = []

    monkeypatch.setattr(
        "whisper_wayland.application.audio_level_monitor.get_source_volume_percent",
        lambda source: CURRENT_VOLUME,
    )
    monkeypatch.setattr(
        "whisper_wayland.application.audio_level_monitor.set_source_volume_percent",
        lambda source, volume: set_calls.append((source, volume)) or True,
    )

    monitor = AudioLevelMonitor(_config())
    monitor.check_audio(_clipped_wav())

    assert set_calls == [("@DEFAULT_SOURCE@", EXPECTED_REDUCED_VOLUME)]


def test_audio_level_monitor_respects_cooldown(monkeypatch) -> None:
    """Monitor skips checks until interval expires."""
    set_calls = []
    now = iter([0.0, 10.0, 10.0])

    monkeypatch.setattr(
        "whisper_wayland.application.audio_level_monitor.get_source_volume_percent",
        lambda source: CURRENT_VOLUME,
    )
    monkeypatch.setattr(
        "whisper_wayland.application.audio_level_monitor.set_source_volume_percent",
        lambda source, volume: set_calls.append((source, volume)) or True,
    )

    monitor = AudioLevelMonitor(_config(), monotonic=lambda: next(now))
    monitor.check_audio(_clipped_wav())
    monitor.check_audio(_clipped_wav())

    assert set_calls == [("@DEFAULT_SOURCE@", EXPECTED_REDUCED_VOLUME)]


def test_audio_level_monitor_can_warn_without_adjusting(monkeypatch) -> None:
    """Monitor can log suggestion without changing source volume."""
    set_source = unittest.mock.Mock()

    monkeypatch.setattr(
        "whisper_wayland.application.audio_level_monitor.get_source_volume_percent",
        lambda source: CURRENT_VOLUME,
    )
    monkeypatch.setattr(
        "whisper_wayland.application.audio_level_monitor.set_source_volume_percent",
        set_source,
    )

    monitor = AudioLevelMonitor(_config(auto_adjust=False))
    monitor.check_audio(_clipped_wav())

    set_source.assert_not_called()


def test_audio_level_monitor_needs_manage_mics_consent(monkeypatch) -> None:
    """Auto-adjust flag alone does not grant permission to change mic settings."""
    set_source = unittest.mock.Mock()
    config = _config(auto_adjust=True)
    config.audio_level_manage_mics_enabled = False

    monkeypatch.setattr(
        "whisper_wayland.application.audio_level_monitor.get_source_volume_percent",
        lambda source: CURRENT_VOLUME,
    )
    monkeypatch.setattr(
        "whisper_wayland.application.audio_level_monitor.set_source_volume_percent",
        set_source,
    )

    monitor = AudioLevelMonitor(config)
    monitor.check_audio(_clipped_wav())

    set_source.assert_not_called()
