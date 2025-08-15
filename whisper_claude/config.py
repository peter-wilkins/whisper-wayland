"""Configuration management for Whisper Claude service.

Handles environment variable loading and validation with comprehensive
error handling and logging.
"""

import logging
import os
from typing import Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Raised when configuration validation fails."""

    pass


class Config:
    """Configuration manager for Whisper Claude service.

    Loads and validates all configuration from environment variables
    with reasonable defaults and comprehensive error handling.
    """

    def __init__(self, env_file: Optional[str] = None) -> None:
        """Initialize configuration manager.

        Args:
            env_file: Optional path to .env file to load
        """
        self._load_env_file(env_file)
        self._validate_required_config()
        logger.info("Configuration loaded successfully")
        logger.debug(f"Configuration: {self._get_safe_config_summary()}")

    def _load_env_file(self, env_file: Optional[str]) -> None:
        """Load environment variables from .env file if it exists."""
        try:
            if env_file:
                if os.path.exists(env_file):
                    load_dotenv(env_file)
                    logger.debug(f"Loaded environment from {env_file}")
                else:
                    logger.warning(f"Environment file {env_file} not found")
            else:
                # Try to load from default locations
                for default_env in [".env", ".env.local"]:
                    if os.path.exists(default_env):
                        load_dotenv(default_env)
                        logger.debug(f"Loaded environment from {default_env}")
                        break
        except Exception as e:
            logger.error(f"Failed to load environment file: {e}")
            raise ConfigError(f"Environment file loading failed: {e}")

    def _validate_required_config(self) -> None:
        """Validate that all required configuration is present."""
        required_vars = ["OPENAI_API_KEY"]
        missing_vars = []

        for var in required_vars:
            if not getattr(self, var.lower(), None):
                missing_vars.append(var)

        if missing_vars:
            error_msg = (
                f"Missing required environment variables: {', '.join(missing_vars)}"
            )
            logger.error(error_msg)
            raise ConfigError(error_msg)

    def _get_safe_config_summary(self) -> dict:
        """Get configuration summary with sensitive data masked."""
        return {
            "openai_api_key": "***" if self.openai_api_key else None,
            "whisper_model": self.whisper_model,
            "audio_sample_rate": self.audio_sample_rate,
            "audio_chunk_size": self.audio_chunk_size,
            "max_recording_duration": self.max_recording_duration,
            "log_level": self.log_level,
            "hotkey": self.hotkey,
            "service_name": self.service_name,
            "service_description": self.service_description,
            "text_insertion_delay": self.text_insertion_delay,
            "text_insertion_method": self.text_insertion_method,
        }

    # OpenAI Configuration
    @property
    def openai_api_key(self) -> str:
        """OpenAI API key for Whisper service."""
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            logger.error("OPENAI_API_KEY is required but not set")
            raise ConfigError("OPENAI_API_KEY environment variable is required")
        return key

    @property
    def whisper_model(self) -> str:
        """Whisper model to use for transcription."""
        return os.getenv("WHISPER_MODEL", "base").strip()

    # Audio Configuration
    @property
    def audio_sample_rate(self) -> int:
        """Audio recording sample rate in Hz."""
        try:
            rate = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
            if rate <= 0:
                raise ValueError("Sample rate must be positive")
            return rate
        except ValueError as e:
            logger.error(f"Invalid AUDIO_SAMPLE_RATE: {e}")
            raise ConfigError(f"Invalid AUDIO_SAMPLE_RATE: {e}")

    @property
    def audio_chunk_size(self) -> int:
        """Audio buffer chunk size in samples."""
        try:
            chunk_size = int(os.getenv("AUDIO_CHUNK_SIZE", "1024"))
            if chunk_size <= 0:
                raise ValueError("Chunk size must be positive")
            return chunk_size
        except ValueError as e:
            logger.error(f"Invalid AUDIO_CHUNK_SIZE: {e}")
            raise ConfigError(f"Invalid AUDIO_CHUNK_SIZE: {e}")

    @property
    def max_recording_duration(self) -> int:
        """Maximum recording duration in seconds."""
        try:
            duration = int(os.getenv("MAX_RECORDING_DURATION", "30"))
            if duration <= 0:
                raise ValueError("Recording duration must be positive")
            return duration
        except ValueError as e:
            logger.error(f"Invalid MAX_RECORDING_DURATION: {e}")
            raise ConfigError(f"Invalid MAX_RECORDING_DURATION: {e}")

    # Logging Configuration
    @property
    def log_level(self) -> str:
        """Logging level."""
        level = os.getenv("LOG_LEVEL", "INFO").upper().strip()
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if level not in valid_levels:
            logger.warning(
                f"Invalid LOG_LEVEL '{level}', using INFO. Valid levels: {valid_levels}"
            )
            return "INFO"
        return level

    # Hotkey Configuration (for future steps)
    @property
    def hotkey(self) -> str:
        """Push-to-talk key combination."""
        return os.getenv("HOTKEY", "ctrl+alt+space").strip().lower()

    # Service Configuration (for future steps)
    @property
    def service_name(self) -> str:
        """Service name for systemd/docker."""
        return os.getenv("SERVICE_NAME", "whisper-claude").strip()

    @property
    def service_description(self) -> str:
        """Service description."""
        return os.getenv(
            "SERVICE_DESCRIPTION", "Voice-to-text transcription service"
        ).strip()

    # Docker Configuration (for future steps)
    @property
    def docker_audio_device(self) -> str:
        """Docker audio device path."""
        return os.getenv("DOCKER_AUDIO_DEVICE", "/dev/snd").strip()

    @property
    def docker_display_var(self) -> str:
        """Docker display environment variable."""
        return os.getenv("DOCKER_DISPLAY_VAR", "DISPLAY").strip()

    # Text Insertion Configuration (for future steps)
    @property
    def text_insertion_delay(self) -> float:
        """Delay before text insertion in seconds."""
        try:
            delay = float(os.getenv("TEXT_INSERTION_DELAY", "0.1"))
            if delay < 0:
                raise ValueError("Text insertion delay must be non-negative")
            return delay
        except ValueError as e:
            logger.error(f"Invalid TEXT_INSERTION_DELAY: {e}")
            raise ConfigError(f"Invalid TEXT_INSERTION_DELAY: {e}")

    @property
    def text_insertion_method(self) -> str:
        """Text insertion method to use."""
        method = os.getenv("TEXT_INSERTION_METHOD", "wtype").strip().lower()
        valid_methods = ["wtype", "xdotool", "clipboard"]
        if method not in valid_methods:
            logger.warning(
                f"Invalid TEXT_INSERTION_METHOD '{method}', using wtype. "
                f"Valid methods: {valid_methods}"
            )
            return "wtype"
        return method


def get_config(env_file: Optional[str] = None) -> Config:
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
        logger.error(f"Failed to initialize configuration: {e}")
        raise
