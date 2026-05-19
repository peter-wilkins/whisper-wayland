"""Whisper Wayland - Transcription Client

Main transcription client orchestrator that coordinates all transcription components.
"""

import logging
import typing

import openai

import whisper_wayland as ww
from whisper_wayland.transcription_client.client_validator import (
    ClientValidationError,
    ClientValidator,
)
from whisper_wayland.transcription_client.connection_tester import ConnectionTester
from whisper_wayland.transcription_client.transcription_engine import (
    TranscriptionEngine,
    TranscriptionEngineError,
)

_logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Raised when transcription operations fail."""

    pass


class TranscriptionClient:
    """OpenAI Whisper API client for audio transcription.

    Provides audio-to-text transcription with error handling,
    retry logic, and comprehensive logging.
    """

    def __init__(self, config: "ww.Config") -> None:
        """Initialize transcription client with configuration.

        Args:
            config: Configuration instance

        Raises:
            TranscriptionError: If client initialization fails
        """
        self.config = config
        self._client: typing.Optional[openai.OpenAI] = None

        try:
            # Initialize components
            self._client_validator = ClientValidator.new()
            self._client = self._client_validator.initialize_client(config)
            self._transcription_engine = TranscriptionEngine.new(self._client, config)
            self._connection_tester = ConnectionTester.new(self._transcription_engine)

            _logger.info("Transcription client initialized successfully")
            _logger.debug(f"Using Whisper model: {config.whisper_model}")
        except ClientValidationError as e:
            raise TranscriptionError(str(e)) from e
        except Exception as e:
            _logger.error(f"Failed to initialize transcription client: {e}")
            raise TranscriptionError(f"Client initialization failed: {e}") from e

    def transcribe_audio(
        self, audio_data: bytes, language: str = "en", max_retries: int = 3
    ) -> typing.Optional[str]:
        """Transcribe audio data to text using OpenAI Whisper API.

        Args:
            audio_data: Audio data in supported format (WAV, MP3, etc.)
            language: Language code for transcription (default: en)
            max_retries: Maximum number of retry attempts

        Returns:
            Transcribed text or None if transcription fails

        Raises:
            TranscriptionError: If transcription fails after all retries
        """
        try:
            return self._transcription_engine.transcribe_audio(audio_data, language, max_retries)
        except TranscriptionEngineError as e:
            raise TranscriptionError(str(e)) from e

    def test_connection(self) -> bool:
        """Test connection to OpenAI API with a minimal request.

        Returns:
            True if connection is successful, False otherwise
        """
        return self._connection_tester.test_connection()

    def get_supported_models(self) -> list[str]:
        """Get list of supported Whisper models.

        Returns:
            List of supported model names
        """
        return self._client_validator.get_supported_models()

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes.

        Returns:
            List of ISO language codes supported by Whisper
        """
        return self._client_validator.get_supported_languages()

    # Backward compatibility methods for tests
    def _map_model_name(self, model: str) -> str:
        """Legacy interface for model mapping."""
        from whisper_wayland.transcription_client.model_mapper import ModelMapper

        model_mapper = ModelMapper.new()
        return model_mapper.map_model_name(model)

    def _create_test_audio(self) -> bytes:
        """Legacy interface for test audio creation."""
        from whisper_wayland.transcription_client.test_audio_generator import TestAudioGenerator

        test_generator = TestAudioGenerator.new()
        return test_generator.create_test_audio()

    def close(self) -> None:
        """Clean up client resources."""
        try:
            if self._client:
                # OpenAI client doesn't require explicit cleanup
                self._client = None
                _logger.debug("Transcription client closed successfully")
        except Exception as e:
            _logger.error(f"Error closing transcription client: {e}")

    def __del__(self) -> None:
        """Cleanup resources on object destruction."""
        self.close()

    @staticmethod
    def new(config: "ww.Config") -> "TranscriptionClient":
        """Create and initialize transcription client instance.

        Args:
            config: Configuration instance

        Returns:
            TranscriptionClient instance

        Raises:
            TranscriptionError: If client creation fails
        """
        try:
            return TranscriptionClient(config)
        except Exception as e:
            _logger.error(f"Failed to create transcription client: {e}")
            raise
