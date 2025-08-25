"""OpenAI Whisper API client for transcription services.

Handles audio transcription using OpenAI's Whisper API with comprehensive
error handling and retry logic.
"""

import io
import logging
import struct
import time
import typing

import openai

from . import config as config_module
from . import constants

logger = logging.getLogger(__name__)


class TranscriptionError(Exception):
    """Raised when transcription operations fail."""

    pass


class TranscriptionClient:
    """OpenAI Whisper API client for audio transcription.

    Provides audio-to-text transcription with error handling,
    retry logic, and comprehensive logging.
    """

    def __init__(self, config: config_module.Config) -> None:
        """Initialize transcription client with configuration.

        Args:
            config: Configuration instance

        Raises:
            TranscriptionError: If client initialization fails
        """
        self.config = config
        self._client: typing.Optional[openai.OpenAI] = None

        self._initialize_client()
        logger.info("Transcription client initialized successfully")
        logger.debug(f"Using Whisper model: {config.whisper_model}")

    def _initialize_client(self) -> None:
        """Initialize OpenAI client with error handling."""
        try:
            self._client = openai.OpenAI(api_key=self.config.openai_api_key)
            self._validate_client()
            logger.debug("OpenAI client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize OpenAI client: {e}")
            raise TranscriptionError(f"OpenAI client initialization failed: {e}") from e

    def _validate_client(self) -> None:
        """Validate OpenAI client configuration.

        Raises:
            TranscriptionError: If client validation fails
        """
        if not self._client:
            raise TranscriptionError("OpenAI client not initialized")

        # Validate API key format (basic check)
        api_key = self.config.openai_api_key
        if not api_key.startswith("sk-"):
            logger.warning("API key may not be in expected format")

        # Validate model name
        valid_models = [
            "whisper-1",  # Current API model name
            "tiny",
            "base",
            "small",
            "medium",
            "large",
            "large-v2",
            "large-v3",
        ]

        model = self.config.whisper_model
        if model not in valid_models:
            logger.warning(
                f"Model '{model}' may not be supported. Supported models: {', '.join(valid_models)}"
            )

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
        if not audio_data:
            logger.warning("No audio data provided for transcription")
            return None

        logger.info(f"Starting transcription of {len(audio_data)} bytes audio data")
        logger.debug(
            f"Transcription params: model={self.config.whisper_model}, "
            f"language={language}, max_retries={max_retries}"
        )

        for attempt in range(max_retries + 1):
            try:
                return self._attempt_transcription(audio_data, language)
            except Exception as e:
                if attempt < max_retries:
                    retry_delay = 2**attempt  # Exponential backoff
                    logger.warning(
                        f"Transcription attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error(f"Transcription failed after {max_retries + 1} attempts: {e}")
                    raise TranscriptionError(f"Transcription failed: {e}") from e

        return None

    def _attempt_transcription(self, audio_data: bytes, language: str) -> str:
        """Attempt single transcription request.

        Args:
            audio_data: Audio data to transcribe
            language: Language code for transcription

        Returns:
            Transcribed text

        Raises:
            Exception: If transcription request fails
        """
        if not self._client:
            raise TranscriptionError("OpenAI client not initialized")

        # Create audio file-like object
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"  # Required for OpenAI API

        try:
            # Make transcription request
            response = self._client.audio.transcriptions.create(
                model=self._map_model_name(self.config.whisper_model),
                file=audio_file,
                language=language,
                response_format="text",
            )

            # Extract text from response (should always be string with response_format="text")
            transcribed_text = response.strip()

            if not transcribed_text:
                logger.warning("Empty transcription result received")
                return ""

            logger.info(
                f"Transcription successful: '{transcribed_text[: constants.TEXT_PREVIEW_LENGTH]}"
                f"{'...' if len(transcribed_text) > constants.TEXT_PREVIEW_LENGTH else ''}'"
            )
            logger.debug(f"Full transcription: '{transcribed_text}'")

            return transcribed_text

        except openai.RateLimitError as e:
            logger.error(f"OpenAI API rate limit exceeded: {e}")
            raise TranscriptionError(f"API rate limit exceeded: {e}") from e
        except openai.BadRequestError as e:
            # Handle bad request errors (like invalid file format) as expected failures
            error_msg = str(e)
            if "Invalid file format" in error_msg or "Supported formats" in error_msg:
                logger.warning(f"Invalid audio format provided: {e}")
                return ""  # Return empty string for invalid audio format
            else:
                logger.error(f"OpenAI API bad request error: {e}")
                raise TranscriptionError(f"API bad request error: {e}") from e
        except openai.APIError as e:
            logger.error(f"OpenAI API error: {e}")
            raise TranscriptionError(f"API error: {e}") from e
        except openai.AuthenticationError as e:
            logger.error(f"OpenAI authentication error: {e}")
            raise TranscriptionError(f"Authentication error: {e}") from e
        except Exception as e:
            logger.error(f"Unexpected transcription error: {e}")
            raise TranscriptionError(f"Unexpected error: {e}") from e

    def _map_model_name(self, model: str) -> str:
        """Map configuration model name to OpenAI API model name.

        Args:
            model: Model name from configuration

        Returns:
            API-compatible model name
        """
        # For OpenAI API, the main model is called "whisper-1"
        # Local model names are mapped to this
        model_mapping = {
            "tiny": "whisper-1",
            "base": "whisper-1",
            "small": "whisper-1",
            "medium": "whisper-1",
            "large": "whisper-1",
            "large-v2": "whisper-1",
            "large-v3": "whisper-1",
            "whisper-1": "whisper-1",
        }

        api_model = model_mapping.get(model, "whisper-1")
        if api_model != model:
            logger.debug(f"Mapped model '{model}' to API model '{api_model}'")

        return api_model

    def test_connection(self) -> bool:
        """Test connection to OpenAI API with a minimal request.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Create minimal test audio data (silence)
            test_audio_data = self._create_test_audio()
            result = self.transcribe_audio(test_audio_data, max_retries=1)

            if result is not None:
                logger.info("OpenAI API connection test successful")
                return True
            else:
                logger.warning("OpenAI API connection test returned no result")
                return False

        except Exception as e:
            logger.error(f"OpenAI API connection test failed: {e}")
            return False

    def _create_test_audio(self) -> bytes:
        """Create minimal test audio data for connection testing.

        Returns:
            Minimal WAV audio data
        """
        # Create 1 second of silence at 16kHz, 16-bit mono
        sample_rate = 16000
        duration = 1.0
        num_samples = int(sample_rate * duration)

        # WAV header
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + num_samples * 2,  # File size
            b"WAVE",
            b"fmt ",
            16,  # PCM format chunk size
            1,  # PCM format
            1,  # Mono
            sample_rate,  # Sample rate
            sample_rate * 2,  # Byte rate
            2,  # Block align
            16,  # Bits per sample
            b"data",
            num_samples * 2,  # Data size
        )

        # Silent audio data
        audio_data = b"\x00" * (num_samples * 2)

        return header + audio_data

    def get_supported_models(self) -> list:
        """Get list of supported Whisper models.

        Returns:
            List of supported model names
        """
        return [
            "whisper-1",
            "tiny",
            "base",
            "small",
            "medium",
            "large",
            "large-v2",
            "large-v3",
        ]

    def get_supported_languages(self) -> list:
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

    def close(self) -> None:
        """Clean up client resources."""
        try:
            if self._client:
                # OpenAI client doesn't require explicit cleanup
                self._client = None
                logger.debug("Transcription client closed successfully")
        except Exception as e:
            logger.error(f"Error closing transcription client: {e}")

    def __del__(self) -> None:
        """Cleanup resources on object destruction."""
        self.close()


def create_transcription_client(config: config_module.Config) -> TranscriptionClient:
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
        logger.error(f"Failed to create transcription client: {e}")
        raise
