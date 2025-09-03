"""Whisper Wayland - Audio Recorder (Compatibility Module)

Imports the modularized AudioRecorder class for backward compatibility.
"""

# Import from the new modular structure
from whisper_wayland.audio_recorder.audio_recorder import AudioRecorder, AudioRecordingError  # noqa: F401 I001
