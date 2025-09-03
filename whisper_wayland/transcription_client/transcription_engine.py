"""Whisper Wayland - Transcription Engine

Core transcription logic with retry mechanism and error handling.
"""

import io
import logging
import time
import typing

import openai

import whisper_wayland as ww
from whisper_wayland.transcription_client.model_mapper import ModelMapper

_logger = logging.getLogger(__name__)


class TranscriptionEngineError(Exception):
    """Raised when transcription engine operations fail."""

    pass


class TranscriptionEngine:
    """Core transcription engine with retry logic and error handling."""

    def __init__(self, client: openai.OpenAI, config: "ww.Config") -> None:
        """Initialize transcription engine.

        Args:
            client: OpenAI client instance
            config: Configuration instance
        """
        self._client = client
        self._config = config
        self._model_mapper = ModelMapper.new()

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
            TranscriptionEngineError: If transcription fails after all retries
        """
        if not audio_data:
            _logger.warning("No audio data provided for transcription")
            return None

        _logger.info(f"Starting transcription of {len(audio_data)} bytes audio data")
        _logger.debug(
            f"Transcription params: model={self._config.whisper_model}, "
            f"language={language}, max_retries={max_retries}"
        )

        for attempt in range(max_retries + 1):
            try:
                return self._attempt_transcription(audio_data, language)
            except Exception as e:
                if attempt < max_retries:
                    retry_delay = 2**attempt  # Exponential backoff
                    _logger.warning(
                        f"Transcription attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                else:
                    _logger.error(f"Transcription failed after {max_retries + 1} attempts: {e}")
                    raise TranscriptionEngineError(f"Transcription failed: {e}") from e

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
        # Create audio file-like object
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"  # Required for OpenAI API

        try:
            # Make transcription request
            response = self._client.audio.transcriptions.create(
                model=self._model_mapper.map_model_name(self._config.whisper_model),
                file=audio_file,
                language=language,
                response_format="text",
            )

            # Extract text from response (should always be string with response_format="text")
            transcribed_text = response.strip()

            if not transcribed_text:
                _logger.warning("Empty transcription result received")
                return ""

            _logger.info(
                f"Transcription successful: '{transcribed_text[: ww.Constants.TEXT_PREVIEW_LENGTH]}"
                f"{'...' if len(transcribed_text) > ww.Constants.TEXT_PREVIEW_LENGTH else ''}'"
            )
            _logger.debug(f"Full transcription: '{transcribed_text}'")

            return transcribed_text

        except openai.RateLimitError as e:
            _logger.error(f"OpenAI API rate limit exceeded: {e}")
            raise TranscriptionEngineError(f"API rate limit exceeded: {e}") from e
        except openai.BadRequestError as e:
            # Handle bad request errors (like invalid file format) as expected failures
            error_msg = str(e)
            if "Invalid file format" in error_msg or "Supported formats" in error_msg:
                _logger.warning(f"Invalid audio format provided: {e}")
                return ""  # Return empty string for invalid audio format
            else:
                _logger.error(f"OpenAI API bad request error: {e}")
                raise TranscriptionEngineError(f"API bad request error: {e}") from e
        except openai.APIError as e:
            _logger.error(f"OpenAI API error: {e}")
            raise TranscriptionEngineError(f"API error: {e}") from e
        except openai.AuthenticationError as e:
            _logger.error(f"OpenAI authentication error: {e}")
            raise TranscriptionEngineError(f"Authentication error: {e}") from e
        except Exception as e:
            _logger.error(f"Unexpected transcription error: {e}")
            raise TranscriptionEngineError(f"Unexpected error: {e}") from e

    @staticmethod
    def new(client: openai.OpenAI, config: "ww.Config") -> "TranscriptionEngine":
        """Create transcription engine instance.

        Args:
            client: OpenAI client instance
            config: Configuration instance

        Returns:
            TranscriptionEngine instance
        """
        return TranscriptionEngine(client, config)
