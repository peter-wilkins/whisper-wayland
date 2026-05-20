"""Whisper Wayland - Audio Processor

Handles audio transcription with error handling and logging.
"""

import logging
import typing

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


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
        try:
            _logger.info("Starting audio transcription...")
            transcribed_text = self.transcription_client.transcribe_audio(audio_data)

            if transcribed_text:
                transcribed_text = self.transcription_client.post_process_text(transcribed_text)
                preview_len = ww.Constants.TRANSCRIPTION_PREVIEW_LENGTH
                preview_text = transcribed_text[:preview_len]
                ellipsis = "..." if len(transcribed_text) > preview_len else ""
                _logger.info(f"Transcription completed: '{preview_text}{ellipsis}'")
            else:
                _logger.warning("Transcription returned empty result")

            return transcribed_text

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
