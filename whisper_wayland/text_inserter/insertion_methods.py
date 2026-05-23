"""Whisper Wayland - Insertion Methods

Text insertion method definitions and availability detection.
"""

import enum
import logging
import shutil

_logger = logging.getLogger(__name__)


class TextInsertionMethod(enum.Enum):
    """Available text insertion methods."""

    TMUX = "tmux"  # Direct tmux pane paste, bypasses system clipboard
    WTYPE = "wtype"  # Wayland text insertion (preferred)
    YDOTOOL = "ydotool"  # Universal tool for Wayland/X11
    XDOTOOL = "xdotool"  # X11 text insertion
    CLIPBOARD = "clipboard"  # Clipboard + paste (fallback)


class MethodDetector:
    """Detects available text insertion methods on the system."""

    def __init__(self) -> None:
        """Initialize method detector."""
        pass

    def detect_available_methods(self) -> dict[TextInsertionMethod, bool]:
        """Detect which text insertion methods are available.

        Returns:
            Dictionary mapping methods to availability status
        """
        available_methods: dict[TextInsertionMethod, bool] = {}

        # Check for wtype (Wayland)
        wtype_available = shutil.which("wtype") is not None
        available_methods[TextInsertionMethod.WTYPE] = wtype_available
        if wtype_available:
            _logger.debug("wtype available for Wayland text insertion")

        # Check for ydotool (Universal)
        ydotool_available = shutil.which("ydotool") is not None
        available_methods[TextInsertionMethod.YDOTOOL] = ydotool_available
        if ydotool_available:
            _logger.debug("ydotool available for universal text insertion")

        tmux_available = shutil.which("tmux") is not None
        available_methods[TextInsertionMethod.TMUX] = tmux_available
        if tmux_available:
            _logger.debug("tmux available for direct pane text insertion")

        # Check for xdotool (X11)
        xdotool_available = shutil.which("xdotool") is not None
        available_methods[TextInsertionMethod.XDOTOOL] = xdotool_available
        if xdotool_available:
            _logger.debug("xdotool available for X11 text insertion")

        # Clipboard is always available as fallback
        available_methods[TextInsertionMethod.CLIPBOARD] = True
        _logger.debug("Clipboard fallback method available")

        return available_methods

    def select_preferred_method(
        self, configured_method: str, available_methods: dict[TextInsertionMethod, bool]
    ) -> TextInsertionMethod | None:
        """Select preferred text insertion method based on config and availability.

        Args:
            configured_method: User-configured method preference
            available_methods: Dictionary of available methods

        Returns:
            Preferred method or None if none available
        """
        configured_method_lower = configured_method.lower()

        if configured_method_lower != "auto":
            # Try to use configured method first
            for method in TextInsertionMethod:
                if method.value == configured_method_lower and available_methods.get(method, False):
                    _logger.debug(f"Using configured method: {method.value}")
                    return method

        # Auto-select best available method
        preference_order = [
            TextInsertionMethod.YDOTOOL,  # Direct typing without touching clipboard
            TextInsertionMethod.WTYPE,  # Wayland direct typing
            TextInsertionMethod.XDOTOOL,  # Good for X11
            TextInsertionMethod.CLIPBOARD,  # Fallback
        ]

        for method in preference_order:
            if available_methods.get(method, False):
                _logger.debug(f"Auto-selected method: {method.value}")
                return method

        _logger.warning("No preferred text insertion method found")
        return None

    @staticmethod
    def new() -> "MethodDetector":
        """Create method detector instance.

        Returns:
            MethodDetector instance
        """
        return MethodDetector()
