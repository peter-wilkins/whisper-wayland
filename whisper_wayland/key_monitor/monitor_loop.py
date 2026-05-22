"""Whisper Wayland - Monitor Loop

Main monitoring loop and thread management for keyboard event detection.
"""

import logging
import select
import threading
import typing

try:
    import evdev
except ImportError as e:
    raise ImportError(
        "evdev is required for key monitoring. Install with: pip install evdev or uv add evdev"
    ) from e

from whisper_wayland.key_monitor.device_manager import DeviceManager
from whisper_wayland.key_monitor.event_handler import EventHandler

_logger = logging.getLogger(__name__)


class MonitorLoopError(Exception):
    """Raised when monitor loop operations fail."""

    pass


class MonitorLoop:
    """Manages the main keyboard monitoring loop and threading."""

    def __init__(self, device_manager: DeviceManager, event_handler: EventHandler) -> None:
        """Initialize monitor loop.

        Args:
            device_manager: Device manager instance
            event_handler: Event handler instance
        """
        self._device_manager = device_manager
        self._event_handler = event_handler
        self._monitoring = False
        self._monitor_thread: typing.Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

    def start_monitoring(self) -> None:
        """Start global hotkey monitoring.

        Raises:
            MonitorLoopError: If monitoring fails to start
        """
        with self._lock:
            if self._monitoring:
                _logger.warning("Key monitoring already active")
                return

            try:
                # Find and open keyboard devices
                if not self._device_manager.find_keyboard_devices():
                    raise MonitorLoopError("No keyboard devices found")

                # Reset stop event
                self._stop_event.clear()

                # Start monitoring thread
                self._monitor_thread = threading.Thread(
                    target=self._monitor_loop, daemon=True, name="KeyMonitor"
                )
                self._monitor_thread.start()

                self._monitoring = True
                _logger.info("Global hotkey monitoring started")

            except Exception as e:
                _logger.error(f"Failed to start key monitoring: {e}")
                self._device_manager.cleanup_devices()
                raise MonitorLoopError(f"Failed to start key monitoring: {e}") from e

    def stop_monitoring(self) -> None:
        """Stop global hotkey monitoring."""
        with self._lock:
            if not self._monitoring:
                return

            try:
                # Signal monitoring thread to stop
                self._stop_event.set()

                # Wait for monitoring thread to finish
                if self._monitor_thread and self._monitor_thread.is_alive():
                    self._monitor_thread.join(timeout=2.0)

                # Clean up
                self._device_manager.cleanup_devices()
                self._monitoring = False
                self._event_handler.reset_state()
                _logger.info("Global hotkey monitoring stopped")

            except Exception as e:
                _logger.error(f"Error stopping key monitoring: {e}")

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in separate thread."""
        _logger.debug("Starting key monitoring loop")

        try:
            # Create file descriptor mapping
            devices = self._device_manager.get_devices()
            devices_dict = {dev.fd: dev for dev in devices}

            while not self._stop_event.is_set():
                # Wait for input events with timeout
                ready, _, _ = select.select(devices_dict.values(), [], [], 0.1)

                if not ready:
                    continue

                for device in ready:
                    if self._stop_event.is_set():
                        break

                    try:
                        # Read events from device
                        for event in device.read():
                            if event.type == evdev.ecodes.EV_KEY:
                                self._event_handler.handle_key_event(event)
                    except OSError:
                        # Device disconnected
                        _logger.warning(f"Device {device.name} disconnected")
                        devices_dict.pop(device.fd, None)
                        self._device_manager.remove_device(device)
                        if not devices_dict:
                            _logger.error("All keyboard devices disconnected")
                            self._monitoring = False
                            self._stop_event.set()
                            break

        except Exception as e:
            _logger.error(f"Error in monitoring loop: {e}")
        finally:
            _logger.debug("Key monitoring loop stopped")

    def is_monitoring(self) -> bool:
        """Check if monitoring is active.

        Returns:
            True if monitoring is active, False otherwise
        """
        with self._lock:
            return self._monitoring

    @staticmethod
    def new(device_manager: DeviceManager, event_handler: EventHandler) -> "MonitorLoop":
        """Create monitor loop instance.

        Args:
            device_manager: Device manager instance
            event_handler: Event handler instance

        Returns:
            MonitorLoop instance
        """
        return MonitorLoop(device_manager, event_handler)
