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
from dataclasses import dataclass

import openai

import whisper_wayland as ww
from whisper_wayland.transcription_client.model_mapper import ModelMapper

_logger = logging.getLogger(__name__)
DEEPGRAM_TARGET_PREFIX = "deepgram:"
OPENAI_COMPATIBLE_TARGET_PREFIX = "openai-compatible:"
WHISPERCPP_TARGET_PREFIX = "whispercpp:"
OPENAI_COMPATIBLE_DEFAULT_API_KEY = "not-needed"
HTTP_BAD_REQUEST = 400


@dataclass(frozen=True)
class TranscriptionBackend:
    """Backend that produced a transcription result."""

    provider: str
    processor_id: str


@dataclass(frozen=True)
class EngineTranscriptionResult:
    """Text plus the backend that produced it."""

    text: str
    backend: TranscriptionBackend


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
        result = self.transcribe_audio_with_backend(audio_data, language, max_retries)
        return result.text if result else None

    def transcribe_audio_with_backend(
        self,
        audio_data: bytes,
        language: str = "en",
        max_retries: int | None = None,
    ) -> typing.Optional[EngineTranscriptionResult]:
        """Transcribe audio data and report the backend that won."""
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

    def _race_transcriptions(self, audio_data: bytes, language: str) -> EngineTranscriptionResult:
        """Race configured transcription models and return the first successful result."""
        race_models = self._race_models()
        primary_models, fallback_models = self._split_race_and_fallback_models(race_models)

        try:
            return self._race_model_group(audio_data, language, primary_models)
        except TranscriptionEngineError as primary_error:
            if not fallback_models:
                raise

            _logger.warning(
                "Primary transcription race failed; trying fallback models %s: %s",
                ", ".join(fallback_models),
                primary_error,
            )
            try:
                return self._race_model_group(audio_data, language, fallback_models)
            except TranscriptionEngineError as fallback_error:
                raise TranscriptionEngineError(
                    f"{primary_error}; fallback failed: {fallback_error}"
                ) from fallback_error

    def _race_model_group(
        self,
        audio_data: bytes,
        language: str,
        models: list[str],
    ) -> EngineTranscriptionResult:
        """Race one group of models and return the first successful result."""
        if len(models) == 1:
            return self._attempt_transcription(audio_data, language, models[0])

        _logger.info("Racing transcription models: %s", ", ".join(models))
        errors: list[Exception] = []

        executor = futures.ThreadPoolExecutor(max_workers=len(models))
        try:
            future_to_model = {
                executor.submit(
                    self._attempt_transcription,
                    audio_data,
                    language,
                    model,
                ): model
                for model in models
            }

            for completed in futures.as_completed(future_to_model):
                model = future_to_model[completed]
                try:
                    result = completed.result()
                except Exception as e:
                    errors.append(e)
                    _logger.warning("Transcription race model %s failed: %s", model, e)
                    continue

                _logger.info("Transcription race winner: %s", model)
                for pending in future_to_model:
                    if pending is not completed:
                        pending.cancel()
                executor.shutdown(wait=False, cancel_futures=True)
                return result
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        raise TranscriptionEngineError(
            "All transcription race models failed: "
            + "; ".join(str(error) for error in errors)
        )

    @staticmethod
    def _split_race_and_fallback_models(models: list[str]) -> tuple[list[str], list[str]]:
        """Keep CPU-heavy local whisper.cpp targets as fallback-only."""
        primary_models = [
            model for model in models if not model.startswith(WHISPERCPP_TARGET_PREFIX)
        ]
        fallback_models = [
            model for model in models if model.startswith(WHISPERCPP_TARGET_PREFIX)
        ]
        if primary_models:
            return primary_models, fallback_models
        return fallback_models, []

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
    ) -> EngineTranscriptionResult:
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
            if model.startswith(OPENAI_COMPATIBLE_TARGET_PREFIX):
                return self._attempt_openai_compatible_transcription(
                    audio_data,
                    language,
                    model,
                )
            if model.startswith(WHISPERCPP_TARGET_PREFIX):
                return self._attempt_whispercpp_transcription(audio_data, language, model)

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
                return EngineTranscriptionResult(
                    text="",
                    backend=TranscriptionBackend(
                        provider="openai",
                        processor_id=self._model_mapper.map_model_name(model),
                    ),
                )

            _logger.info(
                f"Transcription successful: '{transcribed_text[: ww.Constants.TEXT_PREVIEW_LENGTH]}"
                f"{'...' if len(transcribed_text) > ww.Constants.TEXT_PREVIEW_LENGTH else ''}'"
            )
            _logger.debug(f"Full transcription: '{transcribed_text}'")

            return EngineTranscriptionResult(
                text=transcribed_text,
                backend=TranscriptionBackend(
                    provider="openai",
                    processor_id=self._model_mapper.map_model_name(model),
                ),
            )

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

    def _attempt_openai_compatible_transcription(
        self,
        audio_data: bytes,
        language: str,
        target: str,
    ) -> EngineTranscriptionResult:
        """Attempt transcription against an OpenAI-compatible local/remote server."""
        base_url, model = self._parse_openai_compatible_target(target)
        client = openai.OpenAI(
            api_key=OPENAI_COMPATIBLE_DEFAULT_API_KEY,
            base_url=base_url,
            timeout=self._config.transcription_request_timeout_secs,
            max_retries=0,
        )
        audio_file = io.BytesIO(audio_data)
        audio_file.name = "audio.wav"

        response = client.audio.transcriptions.create(
            model=model,
            file=audio_file,
            language=language,
            response_format="text",
        )
        text = response.strip()
        if not text:
            raise TranscriptionEngineError(
                f"OpenAI-compatible server {base_url} returned an empty transcript"
            )

        _logger.info(
            "OpenAI-compatible transcription successful from %s model=%s: '%s%s'",
            base_url,
            model,
            text[: ww.Constants.TEXT_PREVIEW_LENGTH],
            "..." if len(text) > ww.Constants.TEXT_PREVIEW_LENGTH else "",
        )
        return EngineTranscriptionResult(
            text=text,
            backend=TranscriptionBackend(
                provider="openai-compatible",
                processor_id=model,
            ),
        )

    @staticmethod
    def _parse_openai_compatible_target(target: str) -> tuple[str, str]:
        """Parse openai-compatible:<base-url>#<model> race target."""
        raw_target = target.removeprefix(OPENAI_COMPATIBLE_TARGET_PREFIX).strip()
        if not raw_target:
            raise TranscriptionEngineError("OpenAI-compatible target is empty")

        if "#" in raw_target:
            base_url, model = raw_target.rsplit("#", 1)
            model = model.strip() or "whisper-1"
        else:
            base_url = raw_target
            model = "whisper-1"

        base_url = base_url.rstrip("/")
        if not base_url:
            raise TranscriptionEngineError("OpenAI-compatible base URL is empty")

        return base_url, model

    def _attempt_deepgram_transcription(
        self,
        audio_data: bytes,
        target: str,
    ) -> EngineTranscriptionResult:
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
        return EngineTranscriptionResult(
            text=text,
            backend=TranscriptionBackend(provider="deepgram", processor_id=model),
        )

    def _attempt_whispercpp_transcription(
        self,
        audio_data: bytes,
        language: str,
        target: str,
    ) -> EngineTranscriptionResult:
        """Attempt transcription against a whisper.cpp server /inference endpoint."""
        url = target.removeprefix(WHISPERCPP_TARGET_PREFIX).strip()
        if not url:
            raise TranscriptionEngineError("whisper.cpp target URL is empty")

        body, content_type = self._build_whispercpp_multipart_body(audio_data, language)
        request = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": content_type},
            method="POST",
        )

        try:
            with urllib.request.urlopen(  # noqa: S310 - user-configured local/remote endpoint
                request,
                timeout=self._config.transcription_request_timeout_secs,
            ) as response:
                if getattr(response, "status", 200) >= HTTP_BAD_REQUEST:
                    raise TranscriptionEngineError(
                        f"whisper.cpp server returned HTTP {response.status}"
                    )
                payload = json.load(response)
        except (TimeoutError, urllib.error.URLError, OSError, json.JSONDecodeError) as e:
            raise TranscriptionEngineError(f"whisper.cpp server error: {e}") from e

        text = str(payload.get("text", "")).strip()
        if not text:
            raise TranscriptionEngineError("whisper.cpp returned an empty transcript")

        _logger.info(
            "whisper.cpp transcription successful: '%s%s'",
            text[: ww.Constants.TEXT_PREVIEW_LENGTH],
            "..." if len(text) > ww.Constants.TEXT_PREVIEW_LENGTH else "",
        )
        return EngineTranscriptionResult(
            text=text,
            backend=TranscriptionBackend(
                provider="whisper.cpp",
                processor_id="whisper.cpp",
            ),
        )

    @staticmethod
    def _build_whispercpp_multipart_body(
        audio_data: bytes,
        language: str,
    ) -> tuple[bytes, str]:
        """Build the multipart body expected by whisper.cpp's server endpoint."""
        boundary = "whisper-wayland-boundary"
        parts = [
            (
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
                "Content-Type: audio/wav\r\n\r\n"
            ).encode(),
            audio_data,
            (
                f"\r\n--{boundary}\r\n"
                'Content-Disposition: form-data; name="temperature"\r\n\r\n'
                "0\r\n"
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="response_format"\r\n\r\n'
                "json\r\n"
                f"--{boundary}\r\n"
                'Content-Disposition: form-data; name="language"\r\n\r\n'
                f"{language}\r\n"
                f"--{boundary}--\r\n"
            ).encode(),
        ]
        return b"".join(parts), f"multipart/form-data; boundary={boundary}"

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
