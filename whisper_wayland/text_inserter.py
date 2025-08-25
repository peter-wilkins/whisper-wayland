"""Text insertion functionality for cursor position text input.

Provides universal text insertion using multiple methods for maximum compatibility
across X11 and Wayland environments. Supports wtype, ydotool, xdotool, and
clipboard fallback methods.
"""

import logging
import shutil
import subprocess
import time
from enum import Enum
from typing import Dict, List, Optional

from .config import Config
from .constants import TEXT_PREVIEW_LENGTH

logger = logging.getLogger(__name__)


class TextInsertionMethod(Enum):
    """Available text insertion methods."""

    WTYPE = "wtype"  # Wayland text insertion (preferred)
    YDOTOOL = "ydotool"  # Universal tool for Wayland/X11
    XDOTOOL = "xdotool"  # X11 text insertion
    CLIPBOARD = "clipboard"  # Clipboard + paste (fallback)


class TextInsertionError(Exception):
    """Raised when text insertion operations fail."""

    pass


class TextInserter:
    """Universal text inserter with multiple method support.

    Automatically detects and uses the best available text insertion method
    for the current environment (Wayland/X11). Provides fallback methods
    and comprehensive error handling.
    """

    def __init__(self, config: Config) -> None:
        """Initialize text inserter with configuration.

        Args:
            config: Configuration instance

        Raises:
            TextInsertionError: If no text insertion methods are available
        """
        self.config = config
        self._available_methods: Dict[TextInsertionMethod, bool] = {}
        self._preferred_method: Optional[TextInsertionMethod] = None

        # Detect available methods
        self._detect_available_methods()

        # Set preferred method based on configuration
        self._set_preferred_method()

        if not self._available_methods or not any(self._available_methods.values()):
            raise TextInsertionError("No text insertion methods available")

        logger.info(f"Text inserter initialized with method: {self._preferred_method}")
        available_methods = [
            m.value for m, available in self._available_methods.items() if available
        ]
        logger.debug(f"Available methods: {available_methods}")

    def _detect_available_methods(self) -> None:
        """Detect which text insertion methods are available."""

        # Check for wtype (Wayland)
        wtype_available = shutil.which("wtype") is not None
        self._available_methods[TextInsertionMethod.WTYPE] = wtype_available
        if wtype_available:
            logger.debug("wtype available for Wayland text insertion")

        # Check for ydotool (Universal)
        ydotool_available = shutil.which("ydotool") is not None
        self._available_methods[TextInsertionMethod.YDOTOOL] = ydotool_available
        if ydotool_available:
            logger.debug("ydotool available for universal text insertion")

        # Check for xdotool (X11)
        xdotool_available = shutil.which("xdotool") is not None
        self._available_methods[TextInsertionMethod.XDOTOOL] = xdotool_available
        if xdotool_available:
            logger.debug("xdotool available for X11 text insertion")

        # Clipboard is always available as fallback
        self._available_methods[TextInsertionMethod.CLIPBOARD] = True
        logger.debug("Clipboard fallback method available")

    def _set_preferred_method(self) -> None:
        """Set preferred text insertion method based on config and availability."""
        configured_method = self.config.text_insertion_method.lower()

        # Try to use configured method first
        for method in TextInsertionMethod:
            if method.value == configured_method and self._available_methods.get(method, False):
                self._preferred_method = method
                logger.debug(f"Using configured method: {method.value}")
                return

        # Auto-select best available method
        preference_order = [
            TextInsertionMethod.WTYPE,  # Best for Wayland
            TextInsertionMethod.YDOTOOL,  # Universal
            TextInsertionMethod.XDOTOOL,  # Good for X11
            TextInsertionMethod.CLIPBOARD,  # Fallback
        ]

        for method in preference_order:
            if self._available_methods.get(method, False):
                self._preferred_method = method
                logger.debug(f"Auto-selected method: {method.value}")
                return

        logger.warning("No preferred text insertion method found")

    def insert_text(self, text: str) -> bool:
        """Insert text at current cursor position.

        Args:
            text: Text to insert

        Returns:
            True if text was successfully inserted, False otherwise
        """
        if not text:
            logger.warning("No text provided for insertion")
            return False

        if not self._preferred_method:
            logger.error("No text insertion method available")
            return False

        # Clean text for insertion
        cleaned_text = self._clean_text_for_insertion(text)
        if not cleaned_text:
            logger.warning("Text became empty after cleaning")
            return False

        preview_text = cleaned_text[:TEXT_PREVIEW_LENGTH]
        ellipsis = "..." if len(cleaned_text) > TEXT_PREVIEW_LENGTH else ""
        logger.info(
            f"Inserting text using {self._preferred_method.value}: '{preview_text}{ellipsis}'"
        )

        # Add delay before insertion if configured
        if self.config.text_insertion_delay > 0:
            logger.debug(f"Waiting {self.config.text_insertion_delay}s before text insertion")
            time.sleep(self.config.text_insertion_delay)

        try:
            success = self._insert_with_method(self._preferred_method, cleaned_text)
            if success:
                logger.info("Text insertion successful")
                return True
            else:
                logger.warning(f"Text insertion failed with {self._preferred_method.value}")
                return self._try_fallback_methods(cleaned_text)

        except Exception as e:
            logger.error(f"Error during text insertion with {self._preferred_method.value}: {e}")
            return self._try_fallback_methods(cleaned_text)

    def _clean_text_for_insertion(self, text: str) -> str:
        """Clean and prepare text for insertion.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text safe for insertion
        """
        if not text:
            return ""

        # Strip leading/trailing whitespace
        cleaned = text.strip()

        # Replace multiple spaces with single spaces
        cleaned = " ".join(cleaned.split())

        # Log cleaning if text was modified
        if cleaned != text:
            logger.debug(f"Text cleaned: '{text[:30]}...' -> '{cleaned[:30]}...'")

        return cleaned

    def _insert_with_method(self, method: TextInsertionMethod, text: str) -> bool:
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
            logger.error(f"Command failed for {method.value}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error with {method.value}: {e}")
            return False

    def _insert_with_wtype(self, text: str) -> bool:
        """Insert text using wtype (Wayland).

        Args:
            text: Text to insert

        Returns:
            True if successful
        """
        logger.debug("Inserting text with wtype")
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
        logger.debug("Inserting text with ydotool")
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
        logger.debug("Inserting text with xdotool")
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
        logger.debug("Inserting text via clipboard")
        try:
            # Try wl-copy for Wayland
            if shutil.which("wl-copy"):
                result = subprocess.run(
                    ["wl-copy", text],
                    check=False,
                    capture_output=True,
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

            logger.warning("No clipboard tools available")
            return False

        except Exception as e:
            logger.error(f"Clipboard insertion failed: {e}")
            return False

    def _try_fallback_methods(self, text: str) -> bool:
        """Try fallback text insertion methods.

        Args:
            text: Text to insert

        Returns:
            True if any fallback method succeeded
        """
        logger.info("Trying fallback text insertion methods")

        # Try all other available methods
        fallback_order = [
            TextInsertionMethod.YDOTOOL,
            TextInsertionMethod.WTYPE,
            TextInsertionMethod.XDOTOOL,
            TextInsertionMethod.CLIPBOARD,
        ]

        for method in fallback_order:
            if method != self._preferred_method and self._available_methods.get(method, False):
                logger.debug(f"Trying fallback method: {method.value}")
                try:
                    if self._insert_with_method(method, text):
                        logger.info(f"Fallback method {method.value} succeeded")
                        return True
                except Exception as e:
                    logger.debug(f"Fallback method {method.value} failed: {e}")
                    continue

        logger.error("All text insertion methods failed")
        return False

    def test_insertion(self) -> bool:
        """Test text insertion capability.

        Returns:
            True if text insertion is working, False otherwise
        """
        logger.debug("Testing text insertion capability")

        if not self._preferred_method:
            logger.error("No text insertion method available for testing")
            return False

        try:
            # For testing, we'll just verify the command exists and runs without immediate error
            if self._preferred_method == TextInsertionMethod.WTYPE:
                result = subprocess.run(
                    ["wtype", "--version"], check=False, capture_output=True, timeout=5
                )
                return result.returncode == 0

            elif self._preferred_method == TextInsertionMethod.YDOTOOL:
                result = subprocess.run(
                    ["ydotool", "--help"], check=False, capture_output=True, timeout=5
                )
                return result.returncode == 0

            elif self._preferred_method == TextInsertionMethod.XDOTOOL:
                result = subprocess.run(
                    ["xdotool", "--version"],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0

            elif self._preferred_method == TextInsertionMethod.CLIPBOARD:
                # Test clipboard access
                return shutil.which("wl-copy") is not None or shutil.which("xclip") is not None

        except Exception as e:
            logger.error(f"Text insertion test failed: {e}")
            return False

    def get_available_methods(self) -> List[str]:
        """Get list of available text insertion methods.

        Returns:
            List of available method names
        """
        return [method.value for method, available in self._available_methods.items() if available]

    def get_preferred_method(self) -> Optional[str]:
        """Get the currently preferred text insertion method.

        Returns:
            Name of preferred method or None if none available
        """
        return self._preferred_method.value if self._preferred_method else None

    def close(self) -> None:
        """Clean up text inserter resources."""
        logger.debug("Text inserter cleanup completed")


def create_text_inserter(config: Config) -> TextInserter:
    """Create and initialize text inserter instance.

    Args:
        config: Configuration instance

    Returns:
        TextInserter instance

    Raises:
        TextInsertionError: If no text insertion methods are available
    """
    return TextInserter(config)
