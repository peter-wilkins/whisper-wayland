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
            if preferred_method == TextInsertionMethod.CLIPBOARD:
                # Test clipboard access
                return shutil.which("wl-copy") is not None or shutil.which("xclip") is not None

            commands = {
                TextInsertionMethod.TMUX: ["tmux", "-V"],
                TextInsertionMethod.WTYPE: ["wtype", "--version"],
                TextInsertionMethod.YDOTOOL: ["ydotool", "--help"],
                TextInsertionMethod.XDOTOOL: ["xdotool", "--version"],
            }
            command = commands.get(preferred_method)
            if command:
                result = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    timeout=5,
                )
                return result.returncode == 0

        except Exception as e:
            _logger.error(f"Text insertion test failed: {e}")
            return False

        return False

    @staticmethod
    def new() -> "CapabilityTester":
        """Create capability tester instance.

        Returns:
            CapabilityTester instance
        """
        return CapabilityTester()
