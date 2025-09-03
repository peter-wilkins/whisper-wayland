"""Whisper Wayland - Text Processor

Text cleaning and processing functionality for text insertion.
"""

import logging

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class TextProcessor:
    """Handles text cleaning and processing for insertion."""

    def __init__(self) -> None:
        """Initialize text processor."""
        pass

    def clean_text_for_insertion(self, text: str) -> str:
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
            _logger.debug(f"Text cleaned: '{text[:30]}...' -> '{cleaned[:30]}...'")

        return cleaned

    def format_text_preview(self, text: str) -> str:
        """Format text for logging preview.

        Args:
            text: Text to format

        Returns:
            Formatted preview string
        """
        if not text:
            return ""

        preview_text = text[: ww.Constants.TEXT_PREVIEW_LENGTH]
        ellipsis = "..." if len(text) > ww.Constants.TEXT_PREVIEW_LENGTH else ""
        return f"'{preview_text}{ellipsis}'"

    def validate_text(self, text: str) -> bool:
        """Validate text for insertion.

        Args:
            text: Text to validate

        Returns:
            True if text is valid for insertion
        """
        if not text:
            _logger.warning("No text provided for insertion")
            return False

        cleaned_text = self.clean_text_for_insertion(text)
        if not cleaned_text:
            _logger.warning("Text became empty after cleaning")
            return False

        return True

    @staticmethod
    def new() -> "TextProcessor":
        """Create text processor instance.

        Returns:
            TextProcessor instance
        """
        return TextProcessor()
