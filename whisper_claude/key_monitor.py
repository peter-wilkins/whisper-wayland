"""Key monitoring functionality for global hotkey detection.

This module will be implemented in Step 2 to provide global hotkey
detection using pynput with Wayland compatibility.
"""

import logging
from typing import Callable, Optional

from .config import Config

logger = logging.getLogger(__name__)


class KeyMonitorError(Exception):
    """Raised when key monitoring operations fail."""

    pass


class KeyMonitor:
    """Global hotkey monitor using pynput (placeholder for Step 2).

    This is a placeholder implementation that will be expanded in Step 2
    to provide proper global hotkey detection.
    """

    def __init__(self, config: Config) -> None:
        """Initialize key monitor with configuration.

        Args:
            config: Configuration instance
        """
        self.config = config
        self._callback: Optional[Callable] = None
        logger.info("Key monitor placeholder initialized (Step 2 implementation pending)")

    def set_callback(self, callback: Callable) -> None:
        """Set callback for hotkey events.

        Args:
            callback: Function to call when hotkey is detected
        """
        self._callback = callback
        logger.debug("Key monitor callback set (placeholder)")

    def start_monitoring(self) -> None:
        """Start global hotkey monitoring (placeholder)."""
        logger.info("Key monitoring would start here (Step 2 implementation)")

    def stop_monitoring(self) -> None:
        """Stop global hotkey monitoring (placeholder)."""
        logger.info("Key monitoring would stop here (Step 2 implementation)")

    def is_monitoring(self) -> bool:
        """Check if monitoring is active (placeholder).

        Returns:
            Always False in placeholder implementation
        """
        return False

    def close(self) -> None:
        """Clean up key monitor resources (placeholder)."""
        logger.debug("Key monitor cleanup (placeholder)")


def create_key_monitor(config: Config) -> KeyMonitor:
    """Create and initialize key monitor instance.

    Args:
        config: Configuration instance

    Returns:
        KeyMonitor instance
    """
    return KeyMonitor(config)