"""Whisper Wayland - Transcription Engine

Core transcription logic with retry mechanism and error handling.
"""

import io
import json
import logging
import time
import typing
import urllib.error
import urllib.request
from concurrent import futures

import openai

import whisper_wayland as ww
from whisper_wayland.transcription_client.model_mapper import ModelMapper

_logger = logging.getLogger(__name__)
DEEPGRAM_TARGET_PREFIX = "deepgram:"
HTTP_BAD_REQUEST = 400


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
        self,
        audio_data: bytes,
        language: str = "en",
        max_retries: int | None = None,
    ) -> typing.Optional[str]:
        """Transcribe audio data to text using OpenAI Whisper API.

        Args:
            audio_data: Audio data in supported format (WAV, MP3, etc.)
            language: Language code for transcription (default: en)
            max_retries: Maximum number of retry attempts, or configured default

        Returns:
            Transcribed text or None if transcription fails

        Raises:
            TranscriptionEngineError: If transcription fails after all retries
        """
        if not audio_data:
            _logger.warning("No audio data provided for transcription")
            return None

        _logger.info(f"Starting transcription of {len(audio_data)} bytes audio data")
        if max_retries is None:
            max_retries = self._config.transcription_max_retries
        _logger.debug(
            f"Transcription params: model={self._config.whisper_model}, "
            f"language={language}, max_retries={max_retries}"
        )

        for attempt in range(max_retries + 1):
            try:
                if self._config.transcription_race_models:
                    return self._race_transcriptions(audio_data, language)
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

    def _race_transcriptions(self, audio_data: bytes, language: str) -> str:
        """Race configured transcription models and return the first successful result."""
        race_models = self._race_models()
        if len(race_models) == 1:
            return self._attempt_transcription(audio_data, language, race_models[0])

        _logger.info("Racing transcription models: %s", ", ".join(race_models))
        errors: list[Exception] = []

        executor = futures.ThreadPoolExecutor(max_workers=len(race_models))
        try:
            future_to_model = {
                executor.submit(
                    self._attempt_transcription,
                    audio_data,
                    language,
                    model,
                ): model
                for model in race_models
            }

            for completed in futures.as_completed(future_to_model):
                model = future_to_model[completed]
                try:
                    text = completed.result()
                except Exception as e:
                    errors.append(e)
                    _logger.warning("Transcription race model %s failed: %s", model, e)
                    continue

                _logger.info("Transcription race winner: %s", model)
                for pending in future_to_model:
                    if pending is not completed:
                        pending.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                return text
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        raise TranscriptionEngineError(
            "All transcription race models failed: "
            + "; ".join(str(error) for error in errors)
        )

    def _race_models(self) -> list[str]:
        """Return unique transcription race models with the primary model first."""
        models = [self._config.whisper_model, *self._config.transcription_race_models]
        unique_models = []
        seen = set()
        for model in models:
            if model not in seen:
                unique_models.append(model)
                seen.add(model)
        return unique_models

    def _attempt_transcription(
        self,
        audio_data: bytes,
        language: str,
        model_name: str | None = None,
    ) -> str:
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
            model = model_name or self._config.whisper_model
            if model.startswith(DEEPGRAM_TARGET_PREFIX):
                return self._attempt_deepgram_transcription(audio_data, model)

            # Make transcription request
            response = self._client.audio.transcriptions.create(
                model=self._model_mapper.map_model_name(model),
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

    def _attempt_deepgram_transcription(self, audio_data: bytes, target: str) -> str:
        """Attempt a Deepgram transcription request."""
        if not self._config.deepgram_api_key:
            raise TranscriptionEngineError("Deepgram API key is not configured")

        model = target.removeprefix(DEEPGRAM_TARGET_PREFIX) or "nova-3"
        url = f"https://api.deepgram.com/v1/listen?model={model}&language=en&smart_format=true"
        request = urllib.request.Request(
            url,
            data=audio_data,
            headers={
                "Authorization": f"Token {self._config.deepgram_api_key}",
                "Content-Type": "audio/wav",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(  # noqa: S310 - fixed Deepgram API endpoint
                request,
                timeout=self._config.transcription_request_timeout_secs,
            ) as response:
                if getattr(response, "status", 200) >= HTTP_BAD_REQUEST:
                    raise TranscriptionEngineError(
                        f"Deepgram API returned HTTP {response.status}"
                    )
                payload = json.load(response)
        except (TimeoutError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            raise TranscriptionEngineError(f"Deepgram API error: {e}") from e

        text = (
            payload.get("results", {})
            .get("channels", [{}])[0]
            .get("alternatives", [{}])[0]
            .get("transcript", "")
            .strip()
        )
        if not text:
            raise TranscriptionEngineError("Deepgram returned an empty transcript")

        _logger.info(
            "Deepgram transcription successful: '%s%s'",
            text[: ww.Constants.TEXT_PREVIEW_LENGTH],
            "..." if len(text) > ww.Constants.TEXT_PREVIEW_LENGTH else "",
        )
        return text

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
