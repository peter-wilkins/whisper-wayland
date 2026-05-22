"""Whisper Wayland - Device Manager

Device discovery and management functionality for keyboard input devices.
"""

import logging

try:
    import evdev
except ImportError as e:
    raise ImportError(
        "evdev is required for key monitoring. Install with: pip install evdev or uv add evdev"
    ) from e

_logger = logging.getLogger(__name__)


class DeviceManagerError(Exception):
    """Raised when device management operations fail."""

    pass


class DeviceManager:
    """Manages input device discovery and lifecycle."""

    _INPUT_HOTKEY_CODE_NAMES = (
        "KEY_SPACE",
        "KEY_ENTER",
        "BTN_LEFT",
        "BTN_RIGHT",
        "BTN_MIDDLE",
        "BTN_SIDE",
        "BTN_EXTRA",
        "BTN_FORWARD",
        "BTN_BACK",
        "BTN_TASK",
    )

    def __init__(self) -> None:
        """Initialize device manager."""
        self._devices: list[evdev.InputDevice] = []

    def find_keyboard_devices(self) -> bool:
        """Find and open keyboard or pointer input devices.

        Returns:
            True if devices were found, False otherwise

        Raises:
            DeviceManagerError: If device access fails due to permissions or other errors
        """
        devices_found = []

        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

            for device in devices:
                # Check if device has hotkey-capable input events.
                capabilities = device.capabilities()
                if evdev.ecodes.EV_KEY in capabilities:
                    keys = capabilities[evdev.ecodes.EV_KEY]
                    if self._has_hotkey_capable_input(keys):
                        devices_found.append(device)
                        _logger.debug(f"Found input device: {device.name} ({device.path})")

        except PermissionError as e:
            _logger.error(f"Permission denied accessing input devices: {e}")
            _logger.error("Try running with elevated permissions or add user to input group")
            raise DeviceManagerError(f"Permission denied accessing input devices: {e}") from e
        except Exception as e:
            _logger.error(f"Error finding keyboard devices: {e}")
            raise DeviceManagerError(f"Error finding keyboard devices: {e}") from e

        if not devices_found:
            _logger.error("No keyboard or pointer devices found")
            raise DeviceManagerError("No keyboard or pointer devices found")

        self._devices = devices_found
        _logger.info(f"Monitoring {len(self._devices)} input device(s)")
        return True

    def get_devices(self) -> list[evdev.InputDevice]:
        """Get list of managed input devices.

        Returns:
            List of keyboard input devices
        """
        return self._devices.copy()

    @classmethod
    def _hotkey_capable_input_codes(cls) -> set[int]:
        codes = set()
        for code_name in cls._INPUT_HOTKEY_CODE_NAMES:
            code = getattr(evdev.ecodes, code_name, None)
            if isinstance(code, int):
                codes.add(code)
        return codes

    @classmethod
    def _has_hotkey_capable_input(cls, keys: list[int]) -> bool:
        return bool(cls._hotkey_capable_input_codes().intersection(keys))

    def remove_device(self, device: evdev.InputDevice) -> None:
        """Remove and close a disconnected input device."""
        try:
            if device in self._devices:
                self._devices.remove(device)
            device.close()
        except Exception as e:
            _logger.debug(f"Error removing device {device.name}: {e}")

    def cleanup_devices(self) -> None:
        """Clean up input devices."""
        for device in self._devices:
            try:
                device.close()
            except Exception as e:
                _logger.debug(f"Error closing device {device.name}: {e}")
        self._devices.clear()

    @staticmethod
    def new() -> "DeviceManager":
        """Create device manager instance.

        Returns:
            DeviceManager instance
        """
        return DeviceManager()
