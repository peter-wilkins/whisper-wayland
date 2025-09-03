"""Whisper Wayland - Event Handler

Keyboard event processing and hotkey state management.
"""

import logging
import threading
import typing

try:
    import evdev
except ImportError as e:
    raise ImportError(
        "evdev is required for key monitoring. Install with: pip install evdev or uv add evdev"
    ) from e

from whisper_wayland.key_monitor.key_mapping import KeyMapping

_logger = logging.getLogger(__name__)


class EventHandler:
    """Handles keyboard events and manages hotkey state."""

    def __init__(self, hotkey_combination: set[str], key_mapping: KeyMapping) -> None:
        """Initialize event handler.

        Args:
            hotkey_combination: Set of key names that form the hotkey
            key_mapping: Key mapping instance for keycode conversion
        """
        self._hotkey_combination = hotkey_combination
        self._key_mapping = key_mapping
        self._pressed_keys: set[str] = set()
        self._hotkey_pressed = False
        self._callback: typing.Optional[typing.Callable[[], None]] = None
        self._release_callback: typing.Optional[typing.Callable[[], None]] = None
        self._lock = threading.Lock()

    def set_callback(self, callback: typing.Callable[[], None]) -> None:
        """Set callback for hotkey press events.

        Args:
            callback: Function to call when hotkey is pressed
        """
        self._callback = callback
        _logger.debug("Key monitor press callback set")

    def set_release_callback(self, callback: typing.Callable[[], None]) -> None:
        """Set callback for hotkey release events.

        Args:
            callback: Function to call when hotkey is released
        """
        self._release_callback = callback
        _logger.debug("Key monitor release callback set")

    def handle_key_event(self, event: evdev.InputEvent) -> None:
        """Handle a keyboard event.

        Args:
            event: evdev keyboard event
        """
        key_name = self._key_mapping.get_key_name(event.code)
        if not key_name:
            return  # Ignore unknown keys

        with self._lock:
            if event.value == 1:  # Key press
                self._pressed_keys.add(key_name)
                _logger.debug(f"Key pressed: {key_name}")
                _logger.debug(f"Currently pressed keys: {self._pressed_keys}")

            elif event.value == 0:  # Key release
                self._pressed_keys.discard(key_name)
                _logger.debug(f"Key released: {key_name}")
                _logger.debug(f"Currently pressed keys: {self._pressed_keys}")

            # Check target combination after each event
            self._check_hotkey_state()

    def _check_hotkey_state(self) -> None:
        """Check if hotkey combination is pressed and trigger callbacks.

        Must be called with _lock held.
        """
        # Check if all hotkey combination keys are pressed
        hotkey_active = self._hotkey_combination.issubset(self._pressed_keys)

        if hotkey_active and not self._hotkey_pressed:
            # Hotkey just pressed
            self._hotkey_pressed = True
            _logger.debug("Hotkey combination pressed")
            if self._callback:
                try:
                    # Call callback in separate thread to avoid blocking key handling
                    threading.Thread(target=self._callback, daemon=True).start()
                except Exception as e:
                    _logger.error(f"Error calling hotkey press callback: {e}")

        elif not hotkey_active and self._hotkey_pressed:
            # Hotkey just released
            self._hotkey_pressed = False
            _logger.debug("Hotkey combination released")
            if self._release_callback:
                try:
                    # Call callback in separate thread to avoid blocking key handling
                    threading.Thread(target=self._release_callback, daemon=True).start()
                except Exception as e:
                    _logger.error(f"Error calling hotkey release callback: {e}")

    def is_hotkey_pressed(self) -> bool:
        """Check if hotkey is currently pressed.

        Returns:
            True if hotkey combination is currently pressed
        """
        with self._lock:
            return self._hotkey_pressed

    def get_pressed_keys(self) -> set[str]:
        """Get currently pressed keys for debugging.

        Returns:
            Set of currently pressed key names
        """
        with self._lock:
            return self._pressed_keys.copy()

    def reset_state(self) -> None:
        """Reset event handler state."""
        with self._lock:
            self._pressed_keys.clear()
            self._hotkey_pressed = False

    @staticmethod
    def new(hotkey_combination: set[str], key_mapping: KeyMapping) -> "EventHandler":
        """Create event handler instance.

        Args:
            hotkey_combination: Set of key names that form the hotkey
            key_mapping: Key mapping instance for keycode conversion

        Returns:
            EventHandler instance
        """
        return EventHandler(hotkey_combination, key_mapping)
