"""Whisper Wayland - Key Monitor

Main key monitor orchestrator that coordinates all key monitoring components.
"""

import logging
import typing

import whisper_wayland as ww
from whisper_wayland.key_monitor.device_manager import DeviceManager, DeviceManagerError
from whisper_wayland.key_monitor.event_handler import EventHandler
from whisper_wayland.key_monitor.key_mapping import KeyMapping, KeyMappingError
from whisper_wayland.key_monitor.monitor_loop import MonitorLoop, MonitorLoopError

_logger = logging.getLogger(__name__)


class KeyMonitorError(Exception):
    """Raised when key monitoring operations fail."""

    pass


class KeyMonitor:
    """Global hotkey monitor using evdev for push-to-talk functionality.

    Monitors for configurable hotkey combinations using Linux evdev interface.
    Provides press/release state management for push-to-talk operation.
    Works on both X11 and Wayland systems.
    """

    def __init__(self, config: "ww.Config") -> None:
        """Initialize key monitor with configuration.

        Args:
            config: Configuration instance

        Raises:
            KeyMonitorError: If hotkey configuration is invalid
        """
        self.config = config

        try:
            # Initialize components
            self._key_mapping = KeyMapping.new()
            self._device_manager = DeviceManager.new()

            # Parse hotkey configuration
            hotkey_combination = self._key_mapping.parse_hotkey_combination(config.hotkey)

            # Initialize event handler and monitor loop
            self._event_handler = EventHandler.new(hotkey_combination, self._key_mapping)
            self._monitor_loop = MonitorLoop.new(self._device_manager, self._event_handler)

            _logger.info(f"Key monitor initialized with hotkey: {config.hotkey}")
        except (KeyMappingError, DeviceManagerError) as e:
            _logger.error(f"Failed to initialize key monitor: {e}")
            raise KeyMonitorError(f"Key monitor initialization failed: {e}") from e
        except Exception as e:
            _logger.error(f"Failed to initialize key monitor: {e}")
            raise KeyMonitorError(f"Key monitor initialization failed: {e}") from e

    def set_callback(self, callback: typing.Callable[[], None]) -> None:
        """Set callback for hotkey press events.

        Args:
            callback: Function to call when hotkey is pressed
        """
        self._event_handler.set_callback(callback)

    def set_release_callback(self, callback: typing.Callable[[], None]) -> None:
        """Set callback for hotkey release events.

        Args:
            callback: Function to call when hotkey is released
        """
        self._event_handler.set_release_callback(callback)

    def start_monitoring(self) -> None:
        """Start global hotkey monitoring.

        Raises:
            KeyMonitorError: If monitoring fails to start
        """
        try:
            self._monitor_loop.start_monitoring()
        except MonitorLoopError as e:
            raise KeyMonitorError(str(e)) from e

    def stop_monitoring(self) -> None:
        """Stop global hotkey monitoring."""
        self._monitor_loop.stop_monitoring()

    def is_monitoring(self) -> bool:
        """Check if monitoring is active.

        Returns:
            True if monitoring is active, False otherwise
        """
        return self._monitor_loop.is_monitoring()

    def is_hotkey_pressed(self) -> bool:
        """Check if hotkey is currently pressed.

        Returns:
            True if hotkey combination is currently pressed
        """
        return self._event_handler.is_hotkey_pressed()

    def get_pressed_keys(self) -> set[str]:
        """Get currently pressed keys for debugging.

        Returns:
            Set of currently pressed key names
        """
        return self._event_handler.get_pressed_keys()

    def close(self) -> None:
        """Clean up key monitor resources."""
        _logger.debug("Closing key monitor")
        self.stop_monitoring()

    @staticmethod
    def new(config: "ww.Config") -> "KeyMonitor":
        """Create and initialize key monitor instance.

        Args:
            config: Configuration instance

        Returns:
            KeyMonitor instance
        """
        return KeyMonitor(config)
