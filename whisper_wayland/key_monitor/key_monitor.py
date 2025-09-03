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

            # Backward compatibility attributes
            self._callback = None
            self._release_callback = None
            self._monitoring = False
            self._hotkey_pressed = False
            self._hotkey_combination = hotkey_combination
            self._devices = []
            self._pressed_keys = set()
            self._lock = self._event_handler._lock
            self._key_map = self._key_mapping._key_map

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

    # Backward compatibility methods for tests
    def _get_key_name(self, keycode: int) -> typing.Optional[str]:
        """Legacy interface for key name conversion."""
        return self._key_mapping.get_key_name(keycode)

    def _check_hotkey_state(self) -> None:
        """Legacy interface for hotkey state checking."""
        # Sync backward compatibility state with event handler
        self._event_handler._pressed_keys = self._pressed_keys.copy()
        self._event_handler._check_hotkey_state()
        # Update backward compatibility state from event handler
        self._hotkey_pressed = self._event_handler._hotkey_pressed

    def _handle_key_event(self, event: typing.Any) -> None:
        """Legacy interface for key event handling."""
        self._event_handler.handle_key_event(event)

    def _cleanup_devices(self) -> None:
        """Legacy interface for device cleanup."""
        self._device_manager.cleanup_devices()

    @property
    def _callback(self) -> typing.Optional[typing.Callable[[], None]]:
        """Legacy attribute access for callback."""
        return getattr(self._event_handler, "_callback", None)

    @_callback.setter
    def _callback(self, value: typing.Optional[typing.Callable[[], None]]) -> None:
        """Legacy attribute setter for callback."""
        if hasattr(self._event_handler, "_callback"):
            self._event_handler._callback = value

    @property
    def _release_callback(self) -> typing.Optional[typing.Callable[[], None]]:
        """Legacy attribute access for release callback."""
        return getattr(self._event_handler, "_release_callback", None)

    @_release_callback.setter
    def _release_callback(self, value: typing.Optional[typing.Callable[[], None]]) -> None:
        """Legacy attribute setter for release callback."""
        if hasattr(self._event_handler, "_release_callback"):
            self._event_handler._release_callback = value

    @property
    def _monitoring(self) -> bool:
        """Legacy attribute access for monitoring state."""
        return self._monitor_loop.is_monitoring()

    @_monitoring.setter
    def _monitoring(self, value: bool) -> None:
        """Legacy attribute setter for monitoring state."""
        # This is read-only through the property interface

    @property
    def _hotkey_pressed(self) -> bool:
        """Legacy attribute access for hotkey pressed state."""
        return self._event_handler.is_hotkey_pressed()

    @_hotkey_pressed.setter
    def _hotkey_pressed(self, value: bool) -> None:
        """Legacy attribute setter for hotkey pressed state."""
        # This is managed by the event handler

    @property
    def _pressed_keys(self) -> set[str]:
        """Legacy attribute access for pressed keys."""
        return self._event_handler.get_pressed_keys()

    @_pressed_keys.setter
    def _pressed_keys(self, value: set[str]) -> None:
        """Legacy attribute setter for pressed keys."""
        # This is managed by the event handler

    @property
    def _devices(self) -> list:
        """Legacy attribute access for devices."""
        return self._device_manager.get_devices()

    @_devices.setter
    def _devices(self, value: list) -> None:
        """Legacy attribute setter for devices."""
        # This is managed by the device manager

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
