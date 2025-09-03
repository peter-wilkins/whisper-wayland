"""Whisper Wayland - Transcription Processor

Coordinates audio transcription and text insertion workflow.
"""

import logging

import whisper_wayland as ww
from whisper_wayland.application.audio_processor import AudioProcessor
from whisper_wayland.application.text_handler import TextHandler

_logger = logging.getLogger(__name__)


class TranscriptionProcessor:
    """Processes audio data through transcription and text insertion."""

    def __init__(
        self,
        transcription_client: "ww.TranscriptionClient",
        text_inserter: "ww.TextInserter",
    ) -> None:
        """Initialize transcription processor.
        
        Args:
            transcription_client: Transcription client instance
            text_inserter: Text inserter instance
        """
        self.audio_processor = AudioProcessor.new(transcription_client)
        self.text_handler = TextHandler.new(text_inserter)

    def process_audio(self, audio_data: bytes) -> None:
        """Process audio data through transcription and text insertion.
        
        Args:
            audio_data: Audio data to process
        """
        try:
            transcribed_text = self.audio_processor.transcribe_audio(audio_data)

            if transcribed_text:
                self.text_handler.insert_text(transcribed_text)
            else:
                _logger.info("No transcription result")
        except Exception as e:
            _logger.error(f"Error processing transcription: {e}")

    def _transcribe_audio(self, audio_data: bytes) -> str | None:
        """Legacy interface for transcription."""
        return self.audio_processor.transcribe_audio(audio_data)

    def _insert_text(self, text: str) -> None:
        """Legacy interface for text insertion."""
        self.text_handler.insert_text(text)

    @staticmethod
    def new(
        transcription_client: "ww.TranscriptionClient",
        text_inserter: "ww.TextInserter",
    ) -> "TranscriptionProcessor":
        """Create transcription processor instance.
        
        Args:
            transcription_client: Transcription client instance
            text_inserter: Text inserter instance
            
        Returns:
            TranscriptionProcessor instance
        """
        return TranscriptionProcessor(transcription_client, text_inserter)