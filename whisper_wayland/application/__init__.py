"""Whisper Wayland - Application Module

Modular application components for better code organization.
"""

from whisper_wayland.application.application import Application as Application
from whisper_wayland.application.audio_processor import AudioProcessor as AudioProcessor
from whisper_wayland.application.component_manager import ComponentManager as ComponentManager
from whisper_wayland.application.hotkey_handler import HotkeyHandler as HotkeyHandler
from whisper_wayland.application.legacy import LegacyRecorder as LegacyRecorder
from whisper_wayland.application.runtime import RuntimeManager as RuntimeManager
from whisper_wayland.application.text_handler import TextHandler as TextHandler
from whisper_wayland.application.transcription_processor import (
    TranscriptionProcessor as TranscriptionProcessor,
)
