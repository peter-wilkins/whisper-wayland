"""Periodic microphone level monitoring for captured audio."""

from __future__ import annotations

import logging
import time
import typing

from whisper_wayland.audio_recorder.level_meter import analyze_wav, recommended_volume_percent
from whisper_wayland.audio_recorder.microphone_calibrator import (
    get_source_volume_percent,
    set_source_volume_percent,
)

_logger = logging.getLogger(__name__)


class AudioLevelMonitor:
    """Checks captured speech levels occasionally and can auto-adjust source volume."""

    def __init__(
        self,
        config: typing.Any,
        monotonic: typing.Callable[[], float] | None = None,
    ) -> None:
        """Initialize monitor from config."""
        self._enabled = config.audio_level_monitor_enabled
        self._auto_adjust = config.audio_level_auto_adjust_enabled
        self._interval_secs = config.audio_level_check_interval_secs
        self._source = config.audio_level_source
        self._monotonic = monotonic or time.monotonic
        self._last_checked_at: float | None = None

    def check_audio(self, audio_data: bytes) -> None:
        """Check audio levels if monitor is enabled and cooldown elapsed."""
        if not self._enabled or not self._should_check():
            return

        self._last_checked_at = self._monotonic()
        try:
            stats = analyze_wav(audio_data)
            current_volume = get_source_volume_percent(self._source)
            _logger.info(
                "Audio level check: verdict=%s rms=%.1fdBFS peak=%.1fdBFS clipping=%.3f%%",
                stats.verdict,
                stats.rms_dbfs,
                stats.peak_dbfs,
                stats.clipping_percent,
            )

            if current_volume is None:
                _logger.warning("Audio level monitor could not read source volume")
                return

            recommended = recommended_volume_percent(stats, current_volume)
            if recommended == current_volume:
                return

            if self._auto_adjust:
                if set_source_volume_percent(self._source, recommended):
                    _logger.info(
                        "Audio level auto-adjust set %s from %d%% to %d%%",
                        self._source,
                        current_volume,
                        recommended,
                    )
                else:
                    _logger.warning(
                        "Audio level auto-adjust failed for %s; suggested %d%%",
                        self._source,
                        recommended,
                    )
            else:
                _logger.info(
                    "Audio level monitor suggests setting %s from %d%% to %d%%",
                    self._source,
                    current_volume,
                    recommended,
                )
        except Exception as e:
            _logger.warning("Audio level check failed: %s", e)

    def _should_check(self) -> bool:
        if self._last_checked_at is None:
            return True
        return (self._monotonic() - self._last_checked_at) >= self._interval_secs

    @staticmethod
    def new(config: typing.Any) -> AudioLevelMonitor:
        """Create audio level monitor."""
        return AudioLevelMonitor(config)
