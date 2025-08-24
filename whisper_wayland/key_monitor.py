"""Key monitoring functionality for global hotkey detection.

Provides global hotkey detection using evdev with push-to-talk functionality.
Supports configurable key combinations and full Wayland compatibility.
"""

import logging
import select
import threading
from typing import Any, Callable, Dict, List, Optional, Set

try:
    import evdev
    from evdev import InputDevice, InputEvent, ecodes
except ImportError:
    raise ImportError(
        "evdev is required for key monitoring. Install with: pip install evdev or uv add evdev"
    )

from .config import Config

logger = logging.getLogger(__name__)


class KeyMonitorError(Exception):
    """Raised when key monitoring operations fail."""

    pass


class KeyMonitor:
    """Global hotkey monitor using evdev for push-to-talk functionality.

    Monitors for configurable hotkey combinations using Linux evdev interface.
    Provides press/release state management for push-to-talk operation.
    Works on both X11 and Wayland systems.
    """

    def __init__(self, config: Config) -> None:
        """Initialize key monitor with configuration.

        Args:
            config: Configuration instance

        Raises:
            KeyMonitorError: If hotkey configuration is invalid
        """
        self.config = config
        self._callback: Optional[Callable[[], None]] = None
        self._release_callback: Optional[Callable[[], None]] = None
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._devices: List[InputDevice] = []
        self._pressed_keys: Set[str] = set()
        self._hotkey_pressed = False
        self._hotkey_combination: Set[str] = set()
        self._lock = threading.Lock()

        # Key code mapping for evdev
        self._key_map = self._build_key_map()

        # Parse hotkey configuration
        try:
            self._parse_hotkey_combination()
            logger.info(f"Key monitor initialized with hotkey: {config.hotkey}")
        except Exception as e:
            logger.error(f"Failed to initialize key monitor: {e}")
            raise KeyMonitorError(f"Key monitor initialization failed: {e}")

    def _build_key_map(self) -> Dict[int, str]:
        """Build mapping from evdev keycodes to key names."""
        key_map = {
            ecodes.KEY_LEFTCTRL: "ctrl",
            ecodes.KEY_RIGHTCTRL: "ctrl",
            ecodes.KEY_LEFTALT: "alt",
            ecodes.KEY_RIGHTALT: "alt",
            ecodes.KEY_LEFTSHIFT: "shift",
            ecodes.KEY_RIGHTSHIFT: "shift",
            ecodes.KEY_SPACE: "space",
            ecodes.KEY_ENTER: "enter",
            ecodes.KEY_ESC: "esc",
            ecodes.KEY_TAB: "tab",
            ecodes.KEY_BACKSPACE: "backspace",
            ecodes.KEY_DELETE: "delete",
            ecodes.KEY_COMPOSE: "compose",  # The compose key
            ecodes.KEY_MENU: "menu",
            # Function keys
            ecodes.KEY_F1: "f1",
            ecodes.KEY_F2: "f2",
            ecodes.KEY_F3: "f3",
            ecodes.KEY_F4: "f4",
            ecodes.KEY_F5: "f5",
            ecodes.KEY_F6: "f6",
            ecodes.KEY_F7: "f7",
            ecodes.KEY_F8: "f8",
            ecodes.KEY_F9: "f9",
            ecodes.KEY_F10: "f10",
            ecodes.KEY_F11: "f11",
            ecodes.KEY_F12: "f12",
        }

        # Add letter keys (keyboard layout order, not alphabetical)
        letter_keys = {
            ecodes.KEY_A: "a",
            ecodes.KEY_B: "b",
            ecodes.KEY_C: "c",
            ecodes.KEY_D: "d",
            ecodes.KEY_E: "e",
            ecodes.KEY_F: "f",
            ecodes.KEY_G: "g",
            ecodes.KEY_H: "h",
            ecodes.KEY_I: "i",
            ecodes.KEY_J: "j",
            ecodes.KEY_K: "k",
            ecodes.KEY_L: "l",
            ecodes.KEY_M: "m",
            ecodes.KEY_N: "n",
            ecodes.KEY_O: "o",
            ecodes.KEY_P: "p",
            ecodes.KEY_Q: "q",
            ecodes.KEY_R: "r",
            ecodes.KEY_S: "s",
            ecodes.KEY_T: "t",
            ecodes.KEY_U: "u",
            ecodes.KEY_V: "v",
            ecodes.KEY_W: "w",
            ecodes.KEY_X: "x",
            ecodes.KEY_Y: "y",
            ecodes.KEY_Z: "z",
        }
        key_map.update(letter_keys)

        # Add number keys
        for i in range(10):
            key_map[ecodes.KEY_1 + i] = str(i + 1)
        key_map[ecodes.KEY_0] = "0"

        return key_map

    def _parse_hotkey_combination(self) -> None:
        """Parse hotkey string into key set for detection.

        Raises:
            KeyMonitorError: If hotkey format is invalid
        """
        hotkey_str = self.config.hotkey.lower().strip()
        if not hotkey_str:
            raise KeyMonitorError("Hotkey cannot be empty")

        # Handle single key (like "compose")
        if "+" not in hotkey_str:
            self._hotkey_combination = {hotkey_str}
        else:
            # Split by '+' and normalize key names
            key_parts = [part.strip() for part in hotkey_str.split("+")]
            if not key_parts:
                raise KeyMonitorError(f"Invalid hotkey format: {hotkey_str}")

            # Map common key names
            key_mapping = {
                "ctrl": "ctrl",
                "control": "ctrl",
                "alt": "alt",
                "shift": "shift",
                "space": "space",
                "enter": "enter",
                "return": "enter",
                "tab": "tab",
                "esc": "esc",
                "escape": "esc",
                "compose": "compose",
                "menu": "menu",
            }

            self._hotkey_combination.clear()
            for part in key_parts:
                if part in key_mapping:
                    self._hotkey_combination.add(key_mapping[part])
                elif len(part) == 1 and part.isalnum():
                    # Single character keys
                    self._hotkey_combination.add(part)
                elif part.startswith("f") and part[1:].isdigit():
                    # Function keys like f1, f2, etc.
                    self._hotkey_combination.add(part)
                else:
                    logger.warning(f"Unknown key in hotkey: {part}")
                    self._hotkey_combination.add(part)

        logger.debug(f"Parsed hotkey combination: {self._hotkey_combination}")

    def _find_keyboard_devices(self) -> bool:
        """Find and open keyboard input devices.

        Returns:
            True if devices were found, False otherwise
        """
        devices_found = []

        try:
            devices = [evdev.InputDevice(path) for path in evdev.list_devices()]

            for device in devices:
                # Check if device has keyboard capabilities
                capabilities = device.capabilities()
                if ecodes.EV_KEY in capabilities:
                    # Check if it has common keyboard keys
                    keys = capabilities[ecodes.EV_KEY]
                    if ecodes.KEY_SPACE in keys or ecodes.KEY_ENTER in keys:
                        devices_found.append(device)
                        logger.debug(
                            f"Found keyboard device: {device.name} ({device.path})"
                        )

        except PermissionError as e:
            logger.error(f"Permission denied accessing input devices: {e}")
            logger.error(
                "Try running with elevated permissions or add user to input group"
            )
            raise KeyMonitorError(f"Permission denied accessing input devices: {e}")
        except Exception as e:
            logger.error(f"Error finding keyboard devices: {e}")
            raise KeyMonitorError(f"Error finding keyboard devices: {e}")

        if not devices_found:
            logger.error("No keyboard devices found")
            raise KeyMonitorError("No keyboard devices found")

        self._devices = devices_found
        logger.info(f"Monitoring {len(self._devices)} keyboard device(s)")
        return True

    def _get_key_name(self, keycode: int) -> Optional[str]:
        """Convert keycode to readable key name.

        Args:
            keycode: evdev keycode

        Returns:
            Key name string or None if not recognized
        """
        if keycode in self._key_map:
            return self._key_map[keycode]

        # Try to get key name from evdev
        try:
            key_val = ecodes.KEY[keycode]

            # Handle different types that evdev might return
            raw_key_name: Any = None
            if isinstance(key_val, tuple) and key_val:
                raw_key_name = key_val[0]
            else:
                raw_key_name = key_val

            # Convert to string regardless of whether it's bytes or str
            if isinstance(raw_key_name, bytes):
                key_name_str = raw_key_name.decode()
            elif isinstance(raw_key_name, str):
                key_name_str = raw_key_name
            else:
                return None

            # Remove KEY_ prefix if present
            if key_name_str.startswith("KEY_"):
                return key_name_str[4:].lower()
            else:
                return key_name_str.lower()

        except (KeyError, UnicodeDecodeError, AttributeError):
            pass

        return None

    def _check_hotkey_state(self) -> None:
        """Check if hotkey combination is pressed and trigger callbacks.

        Must be called with _lock held.
        """
        # Check if all hotkey combination keys are pressed
        hotkey_active = self._hotkey_combination.issubset(self._pressed_keys)

        if hotkey_active and not self._hotkey_pressed:
            # Hotkey just pressed
            self._hotkey_pressed = True
            logger.debug("Hotkey combination pressed")
            if self._callback:
                try:
                    # Call callback in separate thread to avoid blocking key handling
                    threading.Thread(target=self._callback, daemon=True).start()
                except Exception as e:
                    logger.error(f"Error calling hotkey press callback: {e}")

        elif not hotkey_active and self._hotkey_pressed:
            # Hotkey just released
            self._hotkey_pressed = False
            logger.debug("Hotkey combination released")
            if self._release_callback:
                try:
                    # Call callback in separate thread to avoid blocking key handling
                    threading.Thread(target=self._release_callback, daemon=True).start()
                except Exception as e:
                    logger.error(f"Error calling hotkey release callback: {e}")

    def _monitor_loop(self) -> None:
        """Main monitoring loop running in separate thread."""
        logger.debug("Starting key monitoring loop")

        try:
            # Create file descriptor mapping
            devices = {dev.fd: dev for dev in self._devices}

            while not self._stop_event.is_set():
                # Wait for input events with timeout
                ready, _, _ = select.select(devices.values(), [], [], 0.1)

                if not ready:
                    continue

                for device in ready:
                    if self._stop_event.is_set():
                        break

                    try:
                        # Read events from device
                        for event in device.read():
                            if event.type == ecodes.EV_KEY:
                                self._handle_key_event(event)
                    except OSError:
                        # Device disconnected
                        logger.warning(f"Device {device.name} disconnected")
                        continue

        except Exception as e:
            logger.error(f"Error in monitoring loop: {e}")
        finally:
            logger.debug("Key monitoring loop stopped")

    def _handle_key_event(self, event: InputEvent) -> None:
        """Handle a keyboard event.

        Args:
            event: evdev keyboard event
        """
        key_name = self._get_key_name(event.code)
        if not key_name:
            return  # Ignore unknown keys

        with self._lock:
            if event.value == 1:  # Key press
                self._pressed_keys.add(key_name)
                logger.debug(f"Key pressed: {key_name}")
                logger.debug(f"Currently pressed keys: {self._pressed_keys}")

            elif event.value == 0:  # Key release
                self._pressed_keys.discard(key_name)
                logger.debug(f"Key released: {key_name}")
                logger.debug(f"Currently pressed keys: {self._pressed_keys}")

            # Check target combination after each event
            self._check_hotkey_state()

    def set_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for hotkey press events.

        Args:
            callback: Function to call when hotkey is pressed
        """
        self._callback = callback
        logger.debug("Key monitor press callback set")

    def set_release_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for hotkey release events.

        Args:
            callback: Function to call when hotkey is released
        """
        self._release_callback = callback
        logger.debug("Key monitor release callback set")

    def start_monitoring(self) -> None:
        """Start global hotkey monitoring.

        Raises:
            KeyMonitorError: If monitoring fails to start
        """
        with self._lock:
            if self._monitoring:
                logger.warning("Key monitoring already active")
                return

            try:
                # Find and open keyboard devices
                if not self._find_keyboard_devices():
                    raise KeyMonitorError("No keyboard devices found")

                # Reset stop event
                self._stop_event.clear()

                # Start monitoring thread
                self._monitor_thread = threading.Thread(
                    target=self._monitor_loop, daemon=True, name="KeyMonitor"
                )
                self._monitor_thread.start()

                self._monitoring = True
                logger.info(
                    f"Global hotkey monitoring started for: {self.config.hotkey}"
                )

            except Exception as e:
                logger.error(f"Failed to start key monitoring: {e}")
                self._cleanup_devices()
                raise KeyMonitorError(f"Failed to start key monitoring: {e}")

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
                self._cleanup_devices()
                self._monitoring = False
                self._pressed_keys.clear()
                self._hotkey_pressed = False
                logger.info("Global hotkey monitoring stopped")

            except Exception as e:
                logger.error(f"Error stopping key monitoring: {e}")

    def _cleanup_devices(self) -> None:
        """Clean up input devices."""
        for device in self._devices:
            try:
                device.close()
            except Exception as e:
                logger.debug(f"Error closing device {device.name}: {e}")
        self._devices.clear()

    def is_monitoring(self) -> bool:
        """Check if monitoring is active.

        Returns:
            True if monitoring is active, False otherwise
        """
        with self._lock:
            return self._monitoring

    def is_hotkey_pressed(self) -> bool:
        """Check if hotkey is currently pressed.

        Returns:
            True if hotkey combination is currently pressed
        """
        with self._lock:
            return self._hotkey_pressed

    def get_pressed_keys(self) -> Set[str]:
        """Get currently pressed keys for debugging.

        Returns:
            Set of currently pressed key names
        """
        with self._lock:
            return self._pressed_keys.copy()

    def close(self) -> None:
        """Clean up key monitor resources."""
        logger.debug("Closing key monitor")
        self.stop_monitoring()


def create_key_monitor(config: Config) -> KeyMonitor:
    """Create and initialize key monitor instance.

    Args:
        config: Configuration instance

    Returns:
        KeyMonitor instance
    """
    return KeyMonitor(config)
