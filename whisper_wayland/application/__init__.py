"""Whisper Wayland - Application Module

Modular application components for better code organization.
"""

from whisper_wayland.application.application import Application as Application
from whisper_wayland.application.audio_processor import AudioProcessor as AudioProcessor
from whisper_wayland.application.capture_tap import CaptureTap as CaptureTap
from whisper_wayland.application.capture_tap import (
    CaptureTapWriteResult as CaptureTapWriteResult,
)
from whisper_wayland.application.component_manager import ComponentManager as ComponentManager
from whisper_wayland.application.hotkey_handler import HotkeyHandler as HotkeyHandler
from whisper_wayland.application.runtime import RuntimeManager as RuntimeManager
from whisper_wayland.application.status_indicator import StatusIndicator as StatusIndicator
from whisper_wayland.application.text_handler import TextHandler as TextHandler
from whisper_wayland.application.transcription_processor import (
    TranscriptionProcessor as TranscriptionProcessor,
)
