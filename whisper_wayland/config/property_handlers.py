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

    def get_audio_input_device_index(self) -> int | None:
        """Get explicit audio input device index.

        Returns:
            Input device index, or None for automatic selection
        """
        value = os.getenv("AUDIO_INPUT_DEVICE_INDEX", "").strip()
        if not value:
            return None

        try:
            index = int(value)
            if index < 0:
                raise ValueError("Input device index must be non-negative")
            return index
        except ValueError as e:
            _logger.error(f"Invalid AUDIO_INPUT_DEVICE_INDEX: {e}")
            raise PropertyHandlerError(f"Invalid AUDIO_INPUT_DEVICE_INDEX: {e}") from e

    def get_audio_input_device_name(self) -> str:
        """Get explicit audio input device name match.

        Returns:
            Case-insensitive device name substring, or empty string for automatic selection
        """
        return os.getenv("AUDIO_INPUT_DEVICE_NAME", "").strip().lower()

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

    def get_audio_level_monitor_enabled(self) -> bool:
        """Get whether recorded audio level should be checked periodically."""
        value = os.getenv("AUDIO_LEVEL_MONITOR_ENABLED", "false").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def get_audio_level_auto_adjust_enabled(self) -> bool:
        """Get whether microphone source volume may be adjusted automatically."""
        value = os.getenv("AUDIO_LEVEL_AUTO_ADJUST_ENABLED", "false").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def get_audio_level_manage_mics_enabled(self) -> bool:
        """Get explicit consent to change system microphone settings."""
        value = os.getenv("AUDIO_LEVEL_MANAGE_MICS_ENABLED", "false").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def get_audio_level_check_interval_secs(self) -> float:
        """Get minimum seconds between automatic audio level checks."""
        try:
            interval = float(os.getenv("AUDIO_LEVEL_CHECK_INTERVAL_SECS", "900"))
            if interval < 0:
                raise ValueError("Audio level check interval must be non-negative")
            return interval
        except ValueError as e:
            _logger.error(f"Invalid AUDIO_LEVEL_CHECK_INTERVAL_SECS: {e}")
            raise PropertyHandlerError(f"Invalid AUDIO_LEVEL_CHECK_INTERVAL_SECS: {e}") from e

    def get_audio_level_source(self) -> str:
        """Get Pulse/PipeWire source to adjust."""
        return os.getenv("AUDIO_LEVEL_SOURCE", "@DEFAULT_SOURCE@").strip() or "@DEFAULT_SOURCE@"

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
        return os.getenv("STREAMING_TRANSCRIPTION_MODEL", "gpt-realtime-whisper").strip()

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
            timeout = float(os.getenv("STREAMING_COMPLETION_TIMEOUT_SECS", "4"))
            if timeout <= 0:
                raise ValueError("Streaming completion timeout must be positive")
            return timeout
        except ValueError as e:
            _logger.error(f"Invalid STREAMING_COMPLETION_TIMEOUT_SECS: {e}")
            raise PropertyHandlerError(
                f"Invalid STREAMING_COMPLETION_TIMEOUT_SECS: {e}"
            ) from e

    def get_streaming_delta_idle_timeout_secs(self) -> float:
        """Get seconds to wait after the last realtime partial transcript.

        Returns:
            Timeout in seconds
        """
        try:
            timeout = float(os.getenv("STREAMING_DELTA_IDLE_TIMEOUT_SECS", "0.75"))
            if timeout <= 0:
                raise ValueError("Streaming delta idle timeout must be positive")
            return timeout
        except ValueError as e:
            _logger.error(f"Invalid STREAMING_DELTA_IDLE_TIMEOUT_SECS: {e}")
            raise PropertyHandlerError(
                f"Invalid STREAMING_DELTA_IDLE_TIMEOUT_SECS: {e}"
            ) from e

    def get_streaming_turn_detection_enabled(self) -> bool:
        """Get whether server-side VAD should commit chunks on speech pauses."""
        value = os.getenv("STREAMING_TURN_DETECTION_ENABLED", "false").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def get_streaming_vad_silence_duration_ms(self) -> int:
        """Get server-side VAD silence duration in milliseconds."""
        try:
            duration = int(os.getenv("STREAMING_VAD_SILENCE_DURATION_MS", "700"))
            if duration <= 0:
                raise ValueError("Streaming VAD silence duration must be positive")
            return duration
        except ValueError as e:
            _logger.error(f"Invalid STREAMING_VAD_SILENCE_DURATION_MS: {e}")
            raise PropertyHandlerError(
                f"Invalid STREAMING_VAD_SILENCE_DURATION_MS: {e}"
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
        method = os.getenv("TEXT_INSERTION_METHOD", "auto").strip().lower()
        valid_methods = ["auto", "wtype", "ydotool", "xdotool", "clipboard"]
        if method not in valid_methods:
            _logger.warning(
                f"Invalid TEXT_INSERTION_METHOD '{method}', using auto. "
                f"Valid methods: {valid_methods}"
            )
            return "auto"
        return method

    def get_text_paste_hotkey(self) -> str:
        """Get hotkey used to paste clipboard text.

        Returns:
            Paste hotkey string
        """
        hotkey = os.getenv("TEXT_PASTE_HOTKEY", "ctrl+v").strip().lower()
        valid_hotkeys = ["ctrl+v", "ctrl+shift+v"]
        if hotkey not in valid_hotkeys:
            _logger.warning(
                f"Invalid TEXT_PASTE_HOTKEY '{hotkey}', using ctrl+v. "
                f"Valid hotkeys: {valid_hotkeys}"
            )
            return "ctrl+v"
        return hotkey

    def get_text_post_process_mode(self) -> str:
        """Get transcript post-processing mode.

        Returns:
            Post-processing mode: "raw", "clean", "snappy", or "caveman"
        """
        mode = os.getenv("TEXT_POST_PROCESS_MODE", "raw").strip().lower()
        valid_modes = ["raw", "clean", "snappy", "caveman"]
        if mode not in valid_modes:
            _logger.warning(
                f"Invalid TEXT_POST_PROCESS_MODE '{mode}', using raw. "
                f"Valid modes: {valid_modes}"
            )
            return "raw"
        return mode

    def get_text_post_process_model(self) -> str:
        """Get model used for transcript post-processing.

        Returns:
            OpenAI text model name
        """
        return os.getenv("TEXT_POST_PROCESS_MODEL", "gpt-4.1-mini").strip()

    def get_continuum_capture_inlet_dir(self) -> str:
        """Get optional Continuum local capture inlet directory."""
        return os.getenv("CONTINUUM_CAPTURE_INLET_DIR", "").strip()

    @staticmethod
    def new() -> "PropertyHandlers":
        """Create property handlers instance.

        Returns:
            PropertyHandlers instance
        """
        return PropertyHandlers()
