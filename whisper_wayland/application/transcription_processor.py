"""Whisper Wayland - Transcription Processor

Coordinates audio transcription and text insertion workflow.
"""

import logging

import whisper_wayland as ww
from whisper_wayland.application.audio_processor import AudioProcessor
from whisper_wayland.application.text_handler import TextHandler
from whisper_wayland.transcription_client.realtime_streaming_client import (
    RealtimeStreamingTranscriptionClient,
)

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
        self._transcription_client = transcription_client
        streaming_enabled = (
            getattr(transcription_client.config, "streaming_transcription_enabled", False) is True
        )
        self._streaming_client = (
            RealtimeStreamingTranscriptionClient.new(transcription_client.config)
            if streaming_enabled
            else None
        )

    @property
    def streaming_enabled(self) -> bool:
        """Return whether realtime streaming transcription is configured."""
        return self._streaming_client is not None

    def start_streaming(self) -> bool:
        """Start realtime streaming transcription.

        Returns:
            True if streaming microphone capture started.
        """
        if not self._streaming_client:
            return False

        try:
            return self._streaming_client.start()
        except Exception as e:
            _logger.error(f"Failed to start realtime streaming transcription: {e}")
            return False

    def stop_streaming(self) -> None:
        """Stop realtime streaming and insert the final transcript."""
        if not self._streaming_client:
            _logger.warning("Realtime streaming stop requested while streaming is disabled")
            return

        try:
            result = self._streaming_client.stop()
            if result.text:
                processed_text = self._transcription_client.post_process_text(result.text)
                self.text_handler.insert_text(processed_text)
            elif result.fallback_audio:
                self.process_audio(result.fallback_audio)
            elif result.error:
                _logger.error(f"No realtime transcript available: {result.error}")
            else:
                _logger.info("No realtime transcription result")
        except Exception as e:
            _logger.error(f"Error stopping realtime streaming transcription: {e}")

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

    def close(self) -> None:
        """Clean up processor resources."""
        if self._streaming_client:
            self._streaming_client.close()

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
