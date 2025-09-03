"""Whisper Wayland - Capability Tester

Testing functionality for text insertion capabilities and methods.
"""

import logging
import shutil
import subprocess
import typing

from whisper_wayland.text_inserter.insertion_methods import TextInsertionMethod

_logger = logging.getLogger(__name__)


class CapabilityTester:
    """Tests text insertion capabilities and method functionality."""

    def __init__(self) -> None:
        """Initialize capability tester."""
        pass

    def test_insertion_capability(
        self, preferred_method: typing.Optional[TextInsertionMethod]
    ) -> bool:
        """Test text insertion capability.

        Args:
            preferred_method: The preferred method to test

        Returns:
            True if text insertion is working, False otherwise
        """
        _logger.debug("Testing text insertion capability")

        if not preferred_method:
            _logger.error("No text insertion method available for testing")
            return False

        try:
            # For testing, we'll just verify the command exists and runs without immediate error
            if preferred_method == TextInsertionMethod.WTYPE:
                result = subprocess.run(
                    ["wtype", "--version"], check=False, capture_output=True, timeout=5
                )
                return result.returncode == 0

            elif preferred_method == TextInsertionMethod.YDOTOOL:
                result = subprocess.run(
                    ["ydotool", "--help"], check=False, capture_output=True, timeout=5
                )
                return result.returncode == 0

            elif preferred_method == TextInsertionMethod.XDOTOOL:
                result = subprocess.run(
                    ["xdotool", "--version"],
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0

            elif preferred_method == TextInsertionMethod.CLIPBOARD:
                # Test clipboard access
                return shutil.which("wl-copy") is not None or shutil.which("xclip") is not None

        except Exception as e:
            _logger.error(f"Text insertion test failed: {e}")
            return False

    @staticmethod
    def new() -> "CapabilityTester":
        """Create capability tester instance.

        Returns:
            CapabilityTester instance
        """
        return CapabilityTester()
