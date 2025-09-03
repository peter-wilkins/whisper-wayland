"""Whisper Wayland - Audio Recorder Module

Audio recording components using PyAudio for cross-platform audio capture.
"""

from whisper_wayland.audio_recorder.audio_recorder import AudioRecorder, AudioRecordingError

__all__ = ["AudioRecorder", "AudioRecordingError"]
