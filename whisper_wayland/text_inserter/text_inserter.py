"""Whisper Wayland - Text Inserter

Main text inserter orchestrator that coordinates all text insertion components.
"""

import logging
import time
import typing

import whisper_wayland as ww
from whisper_wayland.text_inserter.capability_tester import CapabilityTester
from whisper_wayland.text_inserter.fallback_handler import FallbackHandler
from whisper_wayland.text_inserter.insertion_methods import MethodDetector
from whisper_wayland.text_inserter.method_executors import MethodExecutors
from whisper_wayland.text_inserter.text_processor import TextProcessor

_logger = logging.getLogger(__name__)


class TextInsertionError(Exception):
    """Raised when text insertion operations fail."""

    pass


class TextInserter:
    """Universal text inserter with multiple method support.

    Automatically detects and uses the best available text insertion method
    for the current environment (Wayland/X11). Provides fallback methods
    and comprehensive error handling.
    """

    def __init__(self, config: "ww.Config") -> None:
        """Initialize text inserter with configuration.

        Args:
            config: Configuration instance

        Raises:
            TextInsertionError: If no text insertion methods are available
        """
        self.config = config

        # Initialize components
        self._method_detector = MethodDetector.new()
        self._text_processor = TextProcessor.new()
        self._capability_tester = CapabilityTester.new()

        # Detect available methods
        self._available_methods = self._method_detector.detect_available_methods()
        self._preferred_method = self._method_detector.select_preferred_method(
            config.text_insertion_method, self._available_methods
        )

        # Initialize method executors and fallback handler
        self._method_executors = MethodExecutors.new(self._available_methods)
        self._fallback_handler = FallbackHandler.new(self._method_executors)

        if not self._available_methods or not any(self._available_methods.values()):
            raise TextInsertionError("No text insertion methods available")

        _logger.info(f"Text inserter initialized with method: {self._preferred_method}")
        available_methods = [
            m.value for m, available in self._available_methods.items() if available
        ]
        _logger.debug(f"Available methods: {available_methods}")

    def insert_text(self, text: str) -> bool:
        """Insert text at current cursor position.

        Args:
            text: Text to insert

        Returns:
            True if text was successfully inserted, False otherwise
        """
        if not self._text_processor.validate_text(text):
            return False

        if not self._preferred_method:
            _logger.error("No text insertion method available")
            return False

        # Clean text for insertion
        cleaned_text = self._text_processor.clean_text_for_insertion(text)
        preview_text = self._text_processor.format_text_preview(cleaned_text)

        _logger.info(f"Inserting text using {self._preferred_method.value}: {preview_text}")

        # Add delay before insertion if configured
        if self.config.text_insertion_delay > 0:
            _logger.debug(f"Waiting {self.config.text_insertion_delay}s before text insertion")
            time.sleep(self.config.text_insertion_delay)

        try:
            success = self._method_executors.insert_with_method(
                self._preferred_method, cleaned_text
            )
            if success:
                _logger.info("Text insertion successful")
                return True
            else:
                _logger.warning(f"Text insertion failed with {self._preferred_method.value}")
                return self._fallback_handler.try_fallback_methods(
                    cleaned_text, self._preferred_method, self._available_methods
                )

        except Exception as e:
            _logger.error(f"Error during text insertion with {self._preferred_method.value}: {e}")
            return self._fallback_handler.try_fallback_methods(
                cleaned_text, self._preferred_method, self._available_methods
            )

    def test_insertion(self) -> bool:
        """Test text insertion capability.

        Returns:
            True if text insertion is working, False otherwise
        """
        return self._capability_tester.test_insertion_capability(self._preferred_method)

    def get_available_methods(self) -> list[str]:
        """Get list of available text insertion methods.

        Returns:
            List of available method names
        """
        return [method.value for method, available in self._available_methods.items() if available]

    def get_preferred_method(self) -> typing.Optional[str]:
        """Get the currently preferred text insertion method.

        Returns:
            Name of preferred method or None if none available
        """
        return self._preferred_method.value if self._preferred_method else None

    def close(self) -> None:
        """Clean up text inserter resources."""
        _logger.debug("Text inserter cleanup completed")

    @staticmethod
    def new(config: "ww.Config") -> "TextInserter":
        """Create and initialize text inserter instance.

        Args:
            config: Configuration instance

        Returns:
            TextInserter instance

        Raises:
            TextInsertionError: If no text insertion methods are available
        """
        return TextInserter(config)
