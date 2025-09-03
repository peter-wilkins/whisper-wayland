"""Whisper Wayland - Fallback Handler

Handles fallback text insertion methods when primary method fails.
"""

import logging
import typing

from whisper_wayland.text_inserter.insertion_methods import TextInsertionMethod
from whisper_wayland.text_inserter.method_executors import MethodExecutors

_logger = logging.getLogger(__name__)


class FallbackHandler:
    """Handles fallback text insertion when primary methods fail."""

    def __init__(self, method_executors: MethodExecutors) -> None:
        """Initialize fallback handler.

        Args:
            method_executors: Method executors instance
        """
        self._method_executors = method_executors

    def try_fallback_methods(
        self,
        text: str,
        preferred_method: typing.Optional[TextInsertionMethod],
        available_methods: dict[TextInsertionMethod, bool],
    ) -> bool:
        """Try fallback text insertion methods.

        Args:
            text: Text to insert
            preferred_method: The primary method that failed
            available_methods: Dictionary of available methods

        Returns:
            True if any fallback method succeeded
        """
        _logger.info("Trying fallback text insertion methods")

        # Try all other available methods
        fallback_order = [
            TextInsertionMethod.YDOTOOL,
            TextInsertionMethod.WTYPE,
            TextInsertionMethod.XDOTOOL,
            TextInsertionMethod.CLIPBOARD,
        ]

        for method in fallback_order:
            if method != preferred_method and available_methods.get(method, False):
                _logger.debug(f"Trying fallback method: {method.value}")
                try:
                    if self._method_executors.insert_with_method(method, text):
                        _logger.info(f"Fallback method {method.value} succeeded")
                        return True
                except Exception as e:
                    _logger.debug(f"Fallback method {method.value} failed: {e}")
                    continue

        _logger.error("All text insertion methods failed")
        return False

    @staticmethod
    def new(method_executors: MethodExecutors) -> "FallbackHandler":
        """Create fallback handler instance.

        Args:
            method_executors: Method executors instance

        Returns:
            FallbackHandler instance
        """
        return FallbackHandler(method_executors)
