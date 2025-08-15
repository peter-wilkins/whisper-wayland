"""Key monitoring functionality for global hotkey detection.

Provides global hotkey detection using pynput with push-to-talk functionality.
Supports configurable key combinations and Wayland compatibility.
"""

import logging
import threading
from typing import Any, Callable, Optional, Set

from pynput import keyboard

from .config import Config

logger = logging.getLogger(__name__)


class KeyMonitorError(Exception):
    """Raised when key monitoring operations fail."""

    pass


class KeyMonitor:
    """Global hotkey monitor using pynput for push-to-talk functionality.

    Monitors for configurable hotkey combinations and provides press/release
    state management for push-to-talk operation.
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
        self._listener: Optional[keyboard.Listener] = None
        self._pressed_keys: Set[str] = set()
        self._hotkey_pressed = False
        self._hotkey_combination: Set[str] = set()
        self._lock = threading.Lock()

        # Parse hotkey configuration
        try:
            self._parse_hotkey_combination()
            logger.info(f"Key monitor initialized with hotkey: {config.hotkey}")
        except Exception as e:
            logger.error(f"Failed to initialize key monitor: {e}")
            raise KeyMonitorError(f"Key monitor initialization failed: {e}")

    def _parse_hotkey_combination(self) -> None:
        """Parse hotkey string into key set for detection.

        Raises:
            KeyMonitorError: If hotkey format is invalid
        """
        hotkey_str = self.config.hotkey.lower().strip()
        if not hotkey_str:
            raise KeyMonitorError("Hotkey cannot be empty")

        # Split by '+' and normalize key names
        key_parts = [part.strip() for part in hotkey_str.split("+")]
        if not key_parts:
            raise KeyMonitorError(f"Invalid hotkey format: {hotkey_str}")

        # Map common key names to pynput format
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
        }

        self._hotkey_combination.clear()
        for part in key_parts:
            if part in key_mapping:
                self._hotkey_combination.add(key_mapping[part])
            elif len(part) == 1 and part.isalnum():
                # Single character keys
                self._hotkey_combination.add(part)
            else:
                logger.warning(f"Unknown key in hotkey: {part}")
                self._hotkey_combination.add(part)

        logger.debug(f"Parsed hotkey combination: {self._hotkey_combination}")

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
                self._listener = keyboard.Listener(
                    on_press=self._on_key_press,
                    on_release=self._on_key_release,
                    suppress=False,  # Don't suppress other applications
                )
                self._listener.start()
                self._monitoring = True
                logger.info(
                    f"Global hotkey monitoring started for: {self.config.hotkey}"
                )
            except Exception as e:
                logger.error(f"Failed to start key monitoring: {e}")
                raise KeyMonitorError(f"Failed to start key monitoring: {e}")

    def stop_monitoring(self) -> None:
        """Stop global hotkey monitoring."""
        with self._lock:
            if not self._monitoring:
                return

            try:
                if self._listener:
                    self._listener.stop()
                    self._listener = None
                self._monitoring = False
                self._pressed_keys.clear()
                self._hotkey_pressed = False
                logger.info("Global hotkey monitoring stopped")
            except Exception as e:
                logger.error(f"Error stopping key monitoring: {e}")

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

    def _on_key_press(self, key: Any) -> None:
        """Handle key press events.

        Args:
            key: The pressed key from pynput
        """
        try:
            key_name = self._normalize_key(key)
            if key_name:
                with self._lock:
                    self._pressed_keys.add(key_name)
                    self._check_hotkey_state()
        except Exception as e:
            logger.debug(f"Error processing key press: {e}")

    def _on_key_release(self, key: Any) -> None:
        """Handle key release events.

        Args:
            key: The released key from pynput
        """
        try:
            key_name = self._normalize_key(key)
            if key_name:
                with self._lock:
                    self._pressed_keys.discard(key_name)
                    self._check_hotkey_state()
        except Exception as e:
            logger.debug(f"Error processing key release: {e}")

    def _normalize_key(self, key: Any) -> Optional[str]:
        """Normalize pynput key to string format.

        Args:
            key: Key from pynput listener

        Returns:
            Normalized key name or None if not recognized
        """
        try:
            if hasattr(key, "name"):
                # Special keys (ctrl, alt, space, etc.)
                return str(key.name).lower()
            elif hasattr(key, "char") and key.char:
                # Alphanumeric characters
                return str(key.char).lower()
            else:
                return None
        except AttributeError:
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
