"""Whisper Wayland - Property Handlers

Configuration property handlers for environment variable processing.
"""

import logging
import os

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class PropertyHandlerError(Exception):
    """Raised when property handling fails."""

    pass


class PropertyHandlers:
    """Handles configuration property processing and validation."""

    def __init__(self) -> None:
        """Initialize property handlers."""
        pass

    # OpenAI Configuration
    def get_openai_api_key(self) -> str:
        """Get OpenAI API key for Whisper service.

        Returns:
            OpenAI API key

        Raises:
            PropertyHandlerError: If API key is not set
        """
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            _logger.error("OPENAI_API_KEY is required but not set")
            raise PropertyHandlerError("OPENAI_API_KEY environment variable is required")
        return key

    def get_whisper_model(self) -> str:
        """Get Whisper model to use for transcription.

        Returns:
            Whisper model name
        """
        return os.getenv("WHISPER_MODEL", "gpt-4o-transcribe").strip()

    # Audio Configuration
    def get_audio_sample_rate(self) -> int:
        """Get audio recording sample rate in Hz.

        Returns:
            Audio sample rate

        Raises:
            PropertyHandlerError: If sample rate is invalid
        """
        try:
            rate = int(os.getenv("AUDIO_SAMPLE_RATE", str(ww.Constants.DEFAULT_SAMPLE_RATE)))
            if rate <= 0:
                raise ValueError("Sample rate must be positive")
            return rate
        except ValueError as e:
            _logger.error(f"Invalid AUDIO_SAMPLE_RATE: {e}")
            raise PropertyHandlerError(f"Invalid AUDIO_SAMPLE_RATE: {e}") from e

    def get_audio_chunk_size(self) -> int:
        """Get audio buffer chunk size in samples.

        Returns:
            Audio chunk size

        Raises:
            PropertyHandlerError: If chunk size is invalid
        """
        try:
            chunk_size = int(os.getenv("AUDIO_CHUNK_SIZE", str(ww.Constants.DEFAULT_CHUNK_SIZE)))
            if chunk_size <= 0:
                raise ValueError("Chunk size must be positive")
            return chunk_size
        except ValueError as e:
            _logger.error(f"Invalid AUDIO_CHUNK_SIZE: {e}")
            raise PropertyHandlerError(f"Invalid AUDIO_CHUNK_SIZE: {e}") from e

    def get_max_recording_duration(self) -> int:
        """Get maximum recording duration in seconds.

        Returns:
            Maximum recording duration

        Raises:
            PropertyHandlerError: If duration is invalid
        """
        try:
            duration = int(
                os.getenv("MAX_RECORDING_DURATION", str(ww.Constants.DEFAULT_RECORDING_DURATION))
            )
            if duration <= 0:
                raise ValueError("Recording duration must be positive")
            return duration
        except ValueError as e:
            _logger.error(f"Invalid MAX_RECORDING_DURATION: {e}")
            raise PropertyHandlerError(f"Invalid MAX_RECORDING_DURATION: {e}") from e

    # Logging Configuration
    def get_log_level(self) -> str:
        """Get logging level.

        Returns:
            Logging level string
        """
        level = os.getenv("LOG_LEVEL", "INFO").upper().strip()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            _logger.warning(
                f"Invalid LOG_LEVEL '{level}', using INFO. Valid levels: {valid_levels}"
            )
            return "INFO"
        return level

    # Hotkey Configuration
    def get_hotkey(self) -> str:
        """Get push-to-talk key combination.

        Returns:
            Hotkey combination string
        """
        return os.getenv("HOTKEY", "ctrl+compose").strip().lower()

    def get_hotkey_mode(self) -> str:
        """Get hotkey activation mode.

        Returns:
            Hotkey mode: "push_to_talk" or "toggle"
        """
        mode = os.getenv("HOTKEY_MODE", "push_to_talk").strip().lower()
        valid_modes = ["push_to_talk", "toggle"]
        if mode not in valid_modes:
            _logger.warning(
                f"Invalid HOTKEY_MODE '{mode}', using push_to_talk. Valid modes: {valid_modes}"
            )
            return "push_to_talk"
        return mode

    def get_streaming_transcription_enabled(self) -> bool:
        """Get whether realtime streaming transcription is enabled.

        Returns:
            True if realtime streaming transcription should be attempted
        """
        value = os.getenv("STREAMING_TRANSCRIPTION_ENABLED", "false").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def get_streaming_transcription_model(self) -> str:
        """Get realtime streaming transcription model.

        Returns:
            OpenAI realtime transcription model name
        """
        return os.getenv("STREAMING_TRANSCRIPTION_MODEL", self.get_whisper_model()).strip()

    def get_streaming_sample_rate(self) -> int:
        """Get realtime streaming PCM sample rate.

        Returns:
            Sample rate in Hz
        """
        try:
            rate = int(os.getenv("STREAMING_SAMPLE_RATE", "24000"))
            if rate <= 0:
                raise ValueError("Streaming sample rate must be positive")
            return rate
        except ValueError as e:
            _logger.error(f"Invalid STREAMING_SAMPLE_RATE: {e}")
            raise PropertyHandlerError(f"Invalid STREAMING_SAMPLE_RATE: {e}") from e

    def get_streaming_completion_timeout_secs(self) -> float:
        """Get seconds to wait for final realtime transcript after stopping.

        Returns:
            Timeout in seconds
        """
        try:
            timeout = float(os.getenv("STREAMING_COMPLETION_TIMEOUT_SECS", "15"))
            if timeout <= 0:
                raise ValueError("Streaming completion timeout must be positive")
            return timeout
        except ValueError as e:
            _logger.error(f"Invalid STREAMING_COMPLETION_TIMEOUT_SECS: {e}")
            raise PropertyHandlerError(
                f"Invalid STREAMING_COMPLETION_TIMEOUT_SECS: {e}"
            ) from e

    # Text Insertion Configuration
    def get_text_insertion_delay(self) -> float:
        """Get delay before text insertion in seconds.

        Returns:
            Text insertion delay

        Raises:
            PropertyHandlerError: If delay is invalid
        """
        try:
            delay = float(
                os.getenv("TEXT_INSERTION_DELAY", str(ww.Constants.DEFAULT_TEXT_INSERTION_DELAY))
            )
            if delay < 0:
                raise ValueError("Text insertion delay must be non-negative")
            return delay
        except ValueError as e:
            _logger.error(f"Invalid TEXT_INSERTION_DELAY: {e}")
            raise PropertyHandlerError(f"Invalid TEXT_INSERTION_DELAY: {e}") from e

    def get_text_insertion_method(self) -> str:
        """Get text insertion method to use.

        Returns:
            Text insertion method name
        """
        method = os.getenv("TEXT_INSERTION_METHOD", "ydotool").strip().lower()
        valid_methods = ["wtype", "ydotool", "xdotool", "clipboard"]
        if method not in valid_methods:
            _logger.warning(
                f"Invalid TEXT_INSERTION_METHOD '{method}', using ydotool. "
                f"Valid methods: {valid_methods}"
            )
            return "ydotool"
        return method

    @staticmethod
    def new() -> "PropertyHandlers":
        """Create property handlers instance.

        Returns:
            PropertyHandlers instance
        """
        return PropertyHandlers()
