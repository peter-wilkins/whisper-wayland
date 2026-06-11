"""Whisper Wayland - Config

Main configuration orchestrator that coordinates all configuration components.
"""

import logging
import typing

from whisper_wayland.config.config_validator import ConfigValidationError, ConfigValidator
from whisper_wayland.config.env_loader import EnvLoader, EnvLoaderError
from whisper_wayland.config.logging_setup import LoggingSetup
from whisper_wayland.config.property_handlers import PropertyHandlerError, PropertyHandlers

_logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration validation fails."""

    pass


class Config:
    """Configuration manager for Whisper Wayland service.

    Loads and validates all configuration from environment variables
    with reasonable defaults and comprehensive error handling.
    """

    def __init__(self, env_file: typing.Optional[str] = None) -> None:
        """Initialize configuration manager.

        Args:
            env_file: Optional path to .env file to load

        Raises:
            ConfigError: If configuration is invalid
        """
        try:
            # Initialize components
            self._env_loader = EnvLoader.new()
            self._config_validator = ConfigValidator.new()
            self._property_handlers = PropertyHandlers.new()
            self._logging_setup = LoggingSetup.new()

            # Load environment and validate
            self._env_loader.load_env_file(env_file)
            self._config_validator.validate_required_config(self)

            _logger.info("Configuration loaded successfully")
            _logger.debug(f"Configuration: {self._config_validator.get_safe_config_summary(self)}")
        except (EnvLoaderError, ConfigValidationError, PropertyHandlerError) as e:
            raise ConfigError(str(e)) from e
        except Exception as e:
            _logger.error(f"Failed to initialize configuration: {e}")
            raise ConfigError(f"Configuration initialization failed: {e}") from e

    # OpenAI Configuration
    @property
    def openai_api_key(self) -> str:
        """OpenAI API key for Whisper service."""
        return self._property_handlers.get_openai_api_key()

    @property
    def deepgram_api_key(self) -> str:
        """Optional Deepgram API key for transcription racing."""
        return self._property_handlers.get_deepgram_api_key()

    @property
    def whisper_model(self) -> str:
        """Whisper model to use for transcription."""
        return self._property_handlers.get_whisper_model()

    @property
    def transcription_request_timeout_secs(self) -> float:
        """Per-request timeout for transcription API calls."""
        return self._property_handlers.get_transcription_request_timeout_secs()

    @property
    def transcription_max_retries(self) -> int:
        """Application-level transcription retry count."""
        return self._property_handlers.get_transcription_max_retries()

    @property
    def transcription_race_models(self) -> list[str]:
        """Additional transcription models to race in parallel."""
        return self._property_handlers.get_transcription_race_models()

    @property
    def streaming_transcription_enabled(self) -> bool:
        """Whether realtime streaming transcription should be attempted."""
        return self._property_handlers.get_streaming_transcription_enabled()

    @property
    def streaming_transcription_model(self) -> str:
        """Realtime transcription model to use for streaming sessions."""
        return self._property_handlers.get_streaming_transcription_model()

    @property
    def streaming_sample_rate(self) -> int:
        """Realtime streaming PCM sample rate in Hz."""
        return self._property_handlers.get_streaming_sample_rate()

    @property
    def streaming_completion_timeout_secs(self) -> float:
        """Seconds to wait for final realtime transcript after recording stops."""
        return self._property_handlers.get_streaming_completion_timeout_secs()

    @property
    def streaming_delta_idle_timeout_secs(self) -> float:
        """Seconds to wait after the last realtime partial transcript."""
        return self._property_handlers.get_streaming_delta_idle_timeout_secs()

    @property
    def streaming_turn_detection_enabled(self) -> bool:
        """Whether realtime streaming should commit speech chunks on pauses."""
        return self._property_handlers.get_streaming_turn_detection_enabled()

    @property
    def streaming_vad_silence_duration_ms(self) -> int:
        """Silence duration used for realtime server-side VAD."""
        return self._property_handlers.get_streaming_vad_silence_duration_ms()

    # Audio Configuration
    @property
    def audio_sample_rate(self) -> int:
        """Audio recording sample rate in Hz."""
        return self._property_handlers.get_audio_sample_rate()

    @property
    def audio_chunk_size(self) -> int:
        """Audio buffer chunk size in samples."""
        return self._property_handlers.get_audio_chunk_size()

    @property
    def audio_preroll_seconds(self) -> float:
        """Seconds of local pre-roll audio prepended when recording starts."""
        return self._property_handlers.get_audio_preroll_seconds()

    @property
    def audio_input_device_index(self) -> int | None:
        """Explicit audio input device index, or None for automatic selection."""
        return self._property_handlers.get_audio_input_device_index()

    @property
    def audio_input_device_name(self) -> str:
        """Explicit audio input device name substring, or empty for automatic selection."""
        return self._property_handlers.get_audio_input_device_name()

    @property
    def max_recording_duration(self) -> int:
        """Maximum recording duration in seconds."""
        return self._property_handlers.get_max_recording_duration()

    @property
    def audio_level_monitor_enabled(self) -> bool:
        """Whether captured audio should be level-checked periodically."""
        return self._property_handlers.get_audio_level_monitor_enabled()

    @property
    def audio_level_auto_adjust_enabled(self) -> bool:
        """Whether periodic level checks may adjust source volume."""
        return self._property_handlers.get_audio_level_auto_adjust_enabled()

    @property
    def audio_level_manage_mics_enabled(self) -> bool:
        """Whether this user explicitly allows automatic mic setting changes."""
        return self._property_handlers.get_audio_level_manage_mics_enabled()

    @property
    def audio_level_check_interval_secs(self) -> float:
        """Minimum seconds between automatic level checks."""
        return self._property_handlers.get_audio_level_check_interval_secs()

    @property
    def audio_level_source(self) -> str:
        """Pulse/PipeWire source used for level auto-adjustment."""
        return self._property_handlers.get_audio_level_source()

    @property
    def audio_transcription_normalization_enabled(self) -> bool:
        """Whether audio sent to the transcription provider should be normalized."""
        return self._property_handlers.get_audio_transcription_normalization_enabled()

    @property
    def audio_transcription_normalization_target_rms_dbfs(self) -> float:
        """Target RMS dBFS for transcription-only normalization."""
        return self._property_handlers.get_audio_transcription_normalization_target_rms_dbfs()

    @property
    def audio_transcription_normalization_max_peak_amplitude(self) -> float:
        """Maximum peak amplitude after transcription-only normalization."""
        return (
            self._property_handlers.get_audio_transcription_normalization_max_peak_amplitude()
        )

    @property
    def audio_transcription_normalization_max_gain(self) -> float:
        """Maximum gain multiplier for transcription-only normalization."""
        return self._property_handlers.get_audio_transcription_normalization_max_gain()

    # Logging Configuration
    @property
    def log_level(self) -> str:
        """Logging level."""
        return self._property_handlers.get_log_level()

    # Hotkey Configuration
    @property
    def hotkey(self) -> str:
        """Push-to-talk key combination."""
        return self._property_handlers.get_hotkey()

    @property
    def hotkey_mode(self) -> str:
        """Hotkey activation mode."""
        return self._property_handlers.get_hotkey_mode()

    # Text Insertion Configuration
    @property
    def text_insertion_delay(self) -> float:
        """Delay before text insertion in seconds."""
        return self._property_handlers.get_text_insertion_delay()

    @property
    def text_insertion_method(self) -> str:
        """Text insertion method to use."""
        return self._property_handlers.get_text_insertion_method()

    @property
    def text_tmux_target_pane(self) -> str:
        """Explicit tmux target pane for tmux insertion."""
        return self._property_handlers.get_text_tmux_target_pane()

    @property
    def text_paste_hotkey(self) -> str:
        """Hotkey used to paste clipboard text."""
        return self._property_handlers.get_text_paste_hotkey()

    @property
    def text_insertion_marker_enabled(self) -> bool:
        """Whether inserted text is prefixed with a correlation marker."""
        return self._property_handlers.get_text_insertion_marker_enabled()

    @property
    def text_post_process_mode(self) -> str:
        """Transcript post-processing mode."""
        return self._property_handlers.get_text_post_process_mode()

    @property
    def text_post_process_model(self) -> str:
        """Model used for transcript post-processing."""
        return self._property_handlers.get_text_post_process_model()

    @property
    def text_post_process_openai_api_key(self) -> str:
        """Optional OpenAI API key used only for transcript post-processing."""
        return self._property_handlers.get_text_post_process_openai_api_key()

    @property
    def text_post_process_providers(self) -> list[str]:
        """Ordered transcript rewrite providers."""
        return self._property_handlers.get_text_post_process_providers()

    @property
    def text_post_process_local_api_url(self) -> str:
        """Local transcript rewrite API endpoint."""
        return self._property_handlers.get_text_post_process_local_api_url()

    @property
    def text_post_process_local_api_timeout_secs(self) -> float:
        """Local transcript rewrite API timeout in seconds."""
        return self._property_handlers.get_text_post_process_local_api_timeout_secs()

    @property
    def continuum_capture_inlet_dir(self) -> str:
        """Local Continuum capture inlet directory, blank when disabled."""
        return self._property_handlers.get_continuum_capture_inlet_dir()

    def setup_logging(self, log_file: typing.Optional[str] = None) -> None:
        """Set up logging configuration for the application.

        Args:
            log_file: Optional path to log file for file logging
        """
        self._logging_setup.setup_logging(self.log_level, log_file)

    # Backward compatibility methods for tests
    def _get_safe_config_summary(self) -> dict:
        """Legacy interface for safe config summary."""
        return self._config_validator.get_safe_config_summary(self)

    def _configure_third_party_loggers(self) -> None:
        """Legacy interface for third party logger configuration."""
        self._logging_setup._configure_third_party_loggers()

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """Get a logger instance with the given name.

        Args:
            name: Logger name (typically __name__)

        Returns:
            Logger instance
        """
        return logging.getLogger(name)

    @staticmethod
    def get(env_file: typing.Optional[str] = None) -> "Config":
        """Get configuration instance with optional environment file.

        Args:
            env_file: Optional path to .env file

        Returns:
            Config instance

        Raises:
            ConfigError: If configuration is invalid
        """
        try:
            return Config(env_file)
        except Exception as e:
            _logger.error(f"Failed to initialize configuration: {e}")
            raise
