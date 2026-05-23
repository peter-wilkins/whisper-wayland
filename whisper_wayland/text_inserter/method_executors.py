"""Whisper Wayland - Method Executors

Individual text insertion method implementations.
"""

import logging
import shutil
import subprocess
import time
import typing

from whisper_wayland.text_inserter.insertion_methods import TextInsertionMethod

_logger = logging.getLogger(__name__)


class MethodExecutors:
    """Executes text insertion using various methods."""

    CLIPBOARD_RESTORE_DELAY_SECS = 0.35

    YDOTOOL_PASTE_HOTKEYS = {
        "ctrl+v": ["29:1", "47:1", "47:0", "29:0"],
        "ctrl+shift+v": ["29:1", "42:1", "47:1", "47:0", "42:0", "29:0"],
    }

    def __init__(
        self,
        available_methods: dict[TextInsertionMethod, bool],
        paste_hotkey: str = "ctrl+v",
    ) -> None:
        """Initialize method executors.

        Args:
            available_methods: Dictionary of available methods
            paste_hotkey: Hotkey used to paste clipboard text
        """
        self._available_methods = available_methods
        self._paste_hotkey = paste_hotkey

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
            ["ydotool", "type", "--key-delay", "0", "--key-hold", "0", "--file", "-"],
            check=False,
            input=text,
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
                previous_clipboard = self._read_wayland_clipboard()
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
                        paste_result = subprocess.run(
                            ["ydotool", "key", *self._get_ydotool_paste_sequence()],
                            check=False,
                            capture_output=True,
                            timeout=5,
                        )
                        if paste_result.returncode == 0:
                            self._restore_wayland_clipboard(previous_clipboard)
                            return True
                        _logger.warning(
                            "Wayland clipboard paste hotkey failed with code %s: %s",
                            paste_result.returncode,
                            paste_result.stderr.decode(errors="replace")
                            if isinstance(paste_result.stderr, bytes)
                            else paste_result.stderr,
                        )

            # Try xclip for X11
            if shutil.which("xclip"):
                previous_clipboard = self._read_x11_clipboard()
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
                        paste_result = subprocess.run(
                            ["xdotool", "key", self._paste_hotkey],
                            check=False,
                            capture_output=True,
                            timeout=5,
                        )
                        if paste_result.returncode == 0:
                            self._restore_x11_clipboard(previous_clipboard)
                            return True
                        _logger.warning(
                            "X11 clipboard paste hotkey failed with code %s: %s",
                            paste_result.returncode,
                            paste_result.stderr.decode(errors="replace")
                            if isinstance(paste_result.stderr, bytes)
                            else paste_result.stderr,
                        )

            _logger.warning("No clipboard tools available")
            return False

        except Exception as e:
            _logger.error(f"Clipboard insertion failed: {e}")
            return False

    def _get_ydotool_paste_sequence(self) -> list[str]:
        """Get ydotool key sequence for the configured paste hotkey."""
        return self.YDOTOOL_PASTE_HOTKEYS.get(
            self._paste_hotkey,
            self.YDOTOOL_PASTE_HOTKEYS["ctrl+v"],
        )

    def _read_wayland_clipboard(self) -> typing.Optional[str]:
        """Read current Wayland clipboard contents."""
        if not shutil.which("wl-paste"):
            return None
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            _logger.debug(f"Could not read Wayland clipboard: {e}")
        return None

    def _restore_wayland_clipboard(self, previous_clipboard: typing.Optional[str]) -> None:
        """Restore previous Wayland clipboard contents, or clear transcript from clipboard."""
        time.sleep(self.CLIPBOARD_RESTORE_DELAY_SECS)
        if previous_clipboard is not None:
            self._write_wayland_clipboard(previous_clipboard)
        elif shutil.which("wl-copy"):
            subprocess.run(
                ["wl-copy", "--clear"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )

    def _write_wayland_clipboard(self, text: str) -> None:
        """Write text to the Wayland clipboard."""
        try:
            subprocess.run(
                ["wl-copy"],
                check=False,
                input=text,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
                timeout=5,
            )
        except Exception as e:
            _logger.debug(f"Could not restore Wayland clipboard: {e}")

    def _read_x11_clipboard(self) -> typing.Optional[str]:
        """Read current X11 clipboard contents."""
        if not shutil.which("xclip"):
            return None
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-out"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            if result.returncode == 0:
                return result.stdout
        except Exception as e:
            _logger.debug(f"Could not read X11 clipboard: {e}")
        return None

    def _restore_x11_clipboard(self, previous_clipboard: typing.Optional[str]) -> None:
        """Restore previous X11 clipboard contents, or clear transcript from clipboard."""
        time.sleep(self.CLIPBOARD_RESTORE_DELAY_SECS)
        if previous_clipboard is None:
            previous_clipboard = ""
        try:
            subprocess.run(
                ["xclip", "-selection", "clipboard"],
                check=False,
                input=previous_clipboard,
                text=True,
                capture_output=True,
                timeout=5,
            )
        except Exception as e:
            _logger.debug(f"Could not restore X11 clipboard: {e}")

    @staticmethod
    def new(
        available_methods: dict[TextInsertionMethod, bool],
        paste_hotkey: str = "ctrl+v",
    ) -> "MethodExecutors":
        """Create method executors instance.

        Args:
            available_methods: Dictionary of available methods
            paste_hotkey: Hotkey used to paste clipboard text

        Returns:
            MethodExecutors instance
        """
        return MethodExecutors(available_methods, paste_hotkey)
