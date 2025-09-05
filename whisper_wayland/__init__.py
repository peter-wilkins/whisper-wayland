"""Whisper Wayland - Voice-to-Text Service

A push-to-talk voice transcription service that converts speech to text
and inserts it at the cursor position in any application.
"""

__version__ = "0.1.0"
__author__ = "Roland Tritsch"
__email__ = "roland@tritsch.org"

from whisper_wayland.application.application import Application as Application
from whisper_wayland.audio_recorder import AudioRecorder as AudioRecorder
from whisper_wayland.audio_recorder import AudioRecordingError as AudioRecordingError
from whisper_wayland.config import Config as Config
from whisper_wayland.config import ConfigError as ConfigError
from whisper_wayland.constants import Constants as Constants
from whisper_wayland.key_monitor import KeyMonitor as KeyMonitor
from whisper_wayland.key_monitor import KeyMonitorError as KeyMonitorError
from whisper_wayland.main import main as main
from whisper_wayland.text_inserter import TextInserter as TextInserter
from whisper_wayland.text_inserter import TextInsertionError as TextInsertionError
from whisper_wayland.transcription_client import TranscriptionClient as TranscriptionClient
from whisper_wayland.transcription_client import TranscriptionError as TranscriptionError
