"""Whisper Wayland - Audio Processor

Handles audio transcription with error handling and logging.
"""

import logging
import typing
from dataclasses import dataclass

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BatchTranscriptionResult:
    """Raw and insertion text from a batch transcription."""

    raw_text: str
    insertion_text: str
    post_process_mode: str


class AudioProcessor:
    """Manages audio transcription processing."""

    def __init__(self, transcription_client: "ww.TranscriptionClient") -> None:
        """Initialize audio processor.

        Args:
            transcription_client: Transcription client instance
        """
        self.transcription_client = transcription_client

    def transcribe_audio(self, audio_data: bytes) -> typing.Optional[str]:
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio data

        Returns:
            Transcribed text or None if transcription failed
        """
        result = self.transcribe_audio_with_result(audio_data)
        return result.insertion_text if result else None

    def transcribe_audio_with_result(
        self, audio_data: bytes
    ) -> typing.Optional[BatchTranscriptionResult]:
        """Transcribe audio and preserve raw and post-processed text."""
        try:
            _logger.info("Starting audio transcription...")
            raw_text = self.transcription_client.transcribe_audio(audio_data)

            if raw_text:
                insertion_text = self.transcription_client.post_process_text(raw_text)
                preview_len = ww.Constants.TRANSCRIPTION_PREVIEW_LENGTH
                preview_text = insertion_text[:preview_len]
                ellipsis = "..." if len(insertion_text) > preview_len else ""
                _logger.info(f"Transcription completed: '{preview_text}{ellipsis}'")
                return BatchTranscriptionResult(
                    raw_text=raw_text,
                    insertion_text=insertion_text,
                    post_process_mode=self.transcription_client.config.text_post_process_mode,
                )

            _logger.warning("Transcription returned empty result")
            return None

        except ww.TranscriptionError as e:
            _logger.error(f"Transcription error: {e}")
            return None
        except Exception as e:
            _logger.error(f"Unexpected error during transcription: {e}")
            return None

    @staticmethod
    def new(transcription_client: "ww.TranscriptionClient") -> "AudioProcessor":
        """Create audio processor instance.

        Args:
            transcription_client: Transcription client instance

        Returns:
            AudioProcessor instance
        """
        return AudioProcessor(transcription_client)
