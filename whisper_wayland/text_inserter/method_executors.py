"""Whisper Wayland - Method Executors

Individual text insertion method implementations.
"""

import logging
import shutil
import subprocess

from whisper_wayland.text_inserter.insertion_methods import TextInsertionMethod

_logger = logging.getLogger(__name__)


class MethodExecutors:
    """Executes text insertion using various methods."""

    def __init__(self, available_methods: dict[TextInsertionMethod, bool]) -> None:
        """Initialize method executors.

        Args:
            available_methods: Dictionary of available methods
        """
        self._available_methods = available_methods

    def insert_with_method(self, method: TextInsertionMethod, text: str) -> bool:
        """Insert text using specific method.

        Args:
            method: Text insertion method to use
            text: Text to insert

        Returns:
            True if successful, False otherwise
        """
        try:
            if method == TextInsertionMethod.WTYPE:
                return self._insert_with_wtype(text)
            elif method == TextInsertionMethod.YDOTOOL:
                return self._insert_with_ydotool(text)
            elif method == TextInsertionMethod.XDOTOOL:
                return self._insert_with_xdotool(text)
            elif method == TextInsertionMethod.CLIPBOARD:
                return self._insert_with_clipboard(text)

        except subprocess.CalledProcessError as e:
            _logger.error(f"Command failed for {method.value}: {e}")
            return False
        except Exception as e:
            _logger.error(f"Unexpected error with {method.value}: {e}")
            return False

    def _insert_with_wtype(self, text: str) -> bool:
        """Insert text using wtype (Wayland).

        Args:
            text: Text to insert

        Returns:
            True if successful
        """
        _logger.debug("Inserting text with wtype")
        result = subprocess.run(
            ["wtype", text], check=False, capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0

    def _insert_with_ydotool(self, text: str) -> bool:
        """Insert text using ydotool (Universal).

        Args:
            text: Text to insert

        Returns:
            True if successful
        """
        _logger.debug("Inserting text with ydotool")
        result = subprocess.run(
            ["ydotool", "type", text],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0

    def _insert_with_xdotool(self, text: str) -> bool:
        """Insert text using xdotool (X11).

        Args:
            text: Text to insert

        Returns:
            True if successful
        """
        _logger.debug("Inserting text with xdotool")
        result = subprocess.run(
            ["xdotool", "type", "--delay", "10", text],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0

    def _insert_with_clipboard(self, text: str) -> bool:
        """Insert text using clipboard + paste (fallback).

        Args:
            text: Text to insert

        Returns:
            True if successful
        """
        _logger.debug("Inserting text via clipboard")
        try:
            # Try wl-copy for Wayland
            if shutil.which("wl-copy"):
                result = subprocess.run(
                    ["wl-copy"],
                    check=False,
                    input=text,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    # Send Ctrl+V to paste
                    if self._available_methods.get(TextInsertionMethod.YDOTOOL, False):
                        subprocess.run(
                            [
                                "ydotool",
                                "key",
                                "29:1",
                                "47:1",
                                "47:0",
                                "29:0",
                            ],  # Ctrl+V
                            check=False,
                            capture_output=True,
                            timeout=5,
                        )
                        return True

            # Try xclip for X11
            if shutil.which("xclip"):
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard"],
                    check=False,
                    input=text,
                    text=True,
                    capture_output=True,
                    timeout=5,
                )
                if result.returncode == 0:
                    # Send Ctrl+V to paste
                    if self._available_methods.get(TextInsertionMethod.XDOTOOL, False):
                        subprocess.run(
                            ["xdotool", "key", "ctrl+v"],
                            check=False,
                            capture_output=True,
                            timeout=5,
                        )
                        return True

            _logger.warning("No clipboard tools available")
            return False

        except Exception as e:
            _logger.error(f"Clipboard insertion failed: {e}")
            return False

    @staticmethod
    def new(available_methods: dict[TextInsertionMethod, bool]) -> "MethodExecutors":
        """Create method executors instance.

        Args:
            available_methods: Dictionary of available methods

        Returns:
            MethodExecutors instance
        """
        return MethodExecutors(available_methods)
