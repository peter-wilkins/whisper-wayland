"""Whisper Wayland - Client Validator

OpenAI client initialization and validation functionality.
"""

import logging

import openai

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class ClientValidationError(Exception):
    """Raised when client validation fails."""

    pass


class ClientValidator:
    """Handles OpenAI client initialization and validation."""

    def __init__(self) -> None:
        """Initialize client validator."""
        pass

    def initialize_client(self, config: "ww.Config") -> openai.OpenAI:
        """Initialize OpenAI client with error handling.

        Args:
            config: Configuration instance

        Returns:
            Initialized OpenAI client

        Raises:
            ClientValidationError: If client initialization fails
        """
        try:
            client = openai.OpenAI(api_key=config.openai_api_key)
            self._validate_client_config(config)
            _logger.debug("OpenAI client initialized successfully")
            return client
        except Exception as e:
            _logger.error(f"Failed to initialize OpenAI client: {e}")
            raise ClientValidationError(f"OpenAI client initialization failed: {e}") from e

    def _validate_client_config(self, config: "ww.Config") -> None:
        """Validate OpenAI client configuration.

        Args:
            config: Configuration instance

        Raises:
            ClientValidationError: If client validation fails
        """
        # Validate API key format (basic check)
        api_key = config.openai_api_key
        if not api_key.startswith("sk-"):
            _logger.warning("API key may not be in expected format")

        # Validate model name
        valid_models = [
            "whisper-1",  # Current API model name
            "gpt-realtime-whisper",
            "gpt-4o-transcribe",
            "gpt-4o-mini-transcribe",
            "gpt-4o-transcribe-diarize",
            "tiny",
            "base",
            "small",
            "medium",
            "large",
            "large-v2",
            "large-v3",
        ]

        model = config.whisper_model
        if model not in valid_models:
            _logger.warning(
                f"Model '{model}' may not be supported. Supported models: {', '.join(valid_models)}"
            )

    def get_supported_models(self) -> list[str]:
        """Get list of supported Whisper models.

        Returns:
            List of supported model names
        """
        return [
            "whisper-1",
            "gpt-realtime-whisper",
            "gpt-4o-transcribe",
            "gpt-4o-mini-transcribe",
            "gpt-4o-transcribe-diarize",
            "tiny",
            "base",
            "small",
            "medium",
            "large",
            "large-v2",
            "large-v3",
        ]

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes.

        Returns:
            List of ISO language codes supported by Whisper
        """
        return [
            "en",  # English
            "es",  # Spanish
            "fr",  # French
            "de",  # German
            "it",  # Italian
            "pt",  # Portuguese
            "ru",  # Russian
            "ja",  # Japanese
            "ko",  # Korean
            "zh",  # Chinese
            # Add more as needed
        ]

    @staticmethod
    def new() -> "ClientValidator":
        """Create client validator instance.

        Returns:
            ClientValidator instance
        """
        return ClientValidator()
