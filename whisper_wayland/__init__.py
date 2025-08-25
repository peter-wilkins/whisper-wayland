"""Whisper Wayland - Voice-to-Text Service

A push-to-talk voice transcription service that converts speech to text
and inserts it at the cursor position in any application."""

__version__ = "0.1.0"
__author__ = "Whisper Wayland Team"
__email__ = "support@whisper-wayland.dev"

from . import main
from .main import main as main_function

__all__ = ["main", "main_function"]
