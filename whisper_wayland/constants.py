"""Whisper Wayland - Constants

Defines application-wide constants for audio configuration,
API settings, and system integration parameters.
"""


class Constants:
    """Static class containing all application constants."""

    # Audio Configuration
    DEFAULT_SAMPLE_RATE = 16000
    HIGH_QUALITY_SAMPLE_RATE = 44100
    DEFAULT_CHUNK_SIZE = 1024
    LARGE_CHUNK_SIZE = 2048
    DEFAULT_RECORDING_DURATION = 30
    LONG_RECORDING_DURATION = 60

    # Text Processing
    DEFAULT_TEXT_INSERTION_DELAY = 0.1
    CUSTOM_TEXT_INSERTION_DELAY = 0.5
    TEXT_PREVIEW_LENGTH = 50
    TRANSCRIPTION_PREVIEW_LENGTH = 100

    # System Limits
    WAV_HEADER_SIZE = 44
    MAX_FUNCTION_ARGUMENTS = 5

    # Test Constants
    EXPECTED_DEVICE_COUNT = 2
    EXPECTED_CHANNELS_MONO = 1
    EXPECTED_CHANNELS_STEREO = 2
    EXPECTED_HANDLER_COUNT = 2
    MIN_LOGGER_CALLS = 3
