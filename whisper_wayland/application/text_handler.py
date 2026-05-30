"""Whisper Wayland - Text Handler

Handles text insertion with error handling and user feedback.
"""

import logging

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class TextHandler:
    """Manages text insertion with comprehensive error handling."""

    def __init__(self, text_inserter: "ww.TextInserter") -> None:
        """Initialize text handler.

        Args:
            text_inserter: Text inserter instance
        """
        self.text_inserter = text_inserter

    def insert_text(self, text: str, insertion_target: str | None = None) -> bool:
        """Insert transcribed text at cursor position.

        Args:
            text: Transcribed text to insert
            insertion_target: Optional insertion destination captured at recording start

        Returns:
            True when insertion succeeded, False otherwise.
        """
        try:
            preview_len = ww.Constants.TEXT_PREVIEW_LENGTH
            preview_text = text[:preview_len]
            ellipsis = "..." if len(text) > preview_len else ""
            _logger.info(f"Inserting transcribed text: '{preview_text}{ellipsis}'")
            if insertion_target is None:
                success = self.text_inserter.insert_text(text)
            else:
                success = self.text_inserter.insert_text(text, insertion_target)

            if success:
                _logger.info("Text insertion successful")
                print(f"✓ Inserted: {text}")
                return True
            else:
                _logger.error("Text insertion failed")
                print(f"✗ Failed to insert text: {text}")
                print("Check that you have focus on a text input field")
                return False

        except ww.TextInsertionError as e:
            _logger.error(f"Text insertion error: {e}")
            print(f"Text insertion error: {e}")
            print(f"Transcribed text: {text}")
            return False
        except Exception as e:
            _logger.error(f"Unexpected error during text insertion: {e}")
            print(f"Unexpected error during text insertion: {e}")
            print(f"Transcribed text: {text}")
            return False

    def capture_insertion_target(self) -> str | None:
        """Capture the current insertion target, if the inserter supports it."""
        capture = getattr(self.text_inserter, "capture_insertion_target", None)
        if not callable(capture):
            return None
        return capture()

    @staticmethod
    def new(text_inserter: "ww.TextInserter") -> "TextHandler":
        """Create text handler instance.

        Args:
            text_inserter: Text inserter instance

        Returns:
            TextHandler instance
        """
        return TextHandler(text_inserter)
