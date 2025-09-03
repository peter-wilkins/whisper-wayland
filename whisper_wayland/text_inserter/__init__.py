"""Whisper Wayland - Text Inserter Module

Text insertion components for cross-platform text input using multiple methods.
"""

from whisper_wayland.text_inserter.text_inserter import (
    TextInserter,
    TextInsertionError,
    TextInsertionMethod,
)

__all__ = ["TextInserter", "TextInsertionError", "TextInsertionMethod"]
