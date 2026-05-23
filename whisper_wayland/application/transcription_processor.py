"""Whisper Wayland - Transcription Processor

Coordinates audio transcription and text insertion workflow.
"""

import logging
import typing

import whisper_wayland as ww
from whisper_wayland.application.audio_processor import AudioProcessor
from whisper_wayland.application.capture_tap import CaptureTap
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
        status_indicator: typing.Any = None,
    ) -> None:
        """Initialize transcription processor.

        Args:
            transcription_client: Transcription client instance
            text_inserter: Text inserter instance
            status_indicator: Optional desktop status indicator
        """
        self.audio_processor = AudioProcessor.new(transcription_client)
        self.text_handler = TextHandler.new(text_inserter)
        self.status_indicator = status_indicator
        self._transcription_client = transcription_client
        self._capture_tap = CaptureTap(transcription_client.config)
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
                self._handle_insert_result(self.text_handler.insert_text(processed_text))
            elif result.fallback_audio:
                self.process_audio(result.fallback_audio)
            elif result.chunks_delivered:
                self._show_idle()
            elif result.error:
                _logger.error(f"No realtime transcript available: {result.error}")
                self._show_error("Transcription failed")
            else:
                _logger.info("No realtime transcription result")
                self._show_error("No transcript")
        except Exception as e:
            _logger.error(f"Error stopping realtime streaming transcription: {e}")
            self._show_error("Transcription failed")

    def cancel_streaming(self) -> None:
        """Cancel realtime streaming without transcribing or inserting text."""
        if not self._streaming_client:
            return

        try:
            self._streaming_client.cancel()
            self._show_idle()
        except Exception as e:
            _logger.debug(f"Error cancelling realtime streaming transcription: {e}")
            self._show_idle()

    def process_audio(self, audio_data: bytes) -> None:
        """Process audio data through transcription and text insertion.

        Args:
            audio_data: Audio data to process
        """
        try:
            transcription_result = self.audio_processor.transcribe_audio_with_result(audio_data)

            if transcription_result:
                self._capture_tap.write(
                    audio_data=audio_data,
                    raw_transcript_text=transcription_result.raw_text,
                    insertion_text=transcription_result.insertion_text,
                )
                self._handle_insert_result(
                    self.text_handler.insert_text(transcription_result.insertion_text)
                )
            else:
                _logger.info("No transcription result")
                self._show_error("No transcript")
        except Exception as e:
            _logger.error(f"Error processing transcription: {e}")
            self._show_error("Transcription failed")

    def close(self) -> None:
        """Clean up processor resources."""
        if self._streaming_client:
            self._streaming_client.close()

    def _handle_insert_result(self, success: bool) -> None:
        """Update status indicator after text insertion."""
        if success:
            self._show_idle()
        else:
            self._show_error("Text insertion failed")

    def _show_idle(self) -> None:
        """Update indicator to idle state."""
        if self.status_indicator:
            self.status_indicator.idle()

    def _show_error(self, message: str) -> None:
        """Update indicator to error state."""
        if self.status_indicator:
            self.status_indicator.error(message)

    @staticmethod
    def new(
        transcription_client: "ww.TranscriptionClient",
        text_inserter: "ww.TextInserter",
        status_indicator: typing.Any = None,
    ) -> "TranscriptionProcessor":
        """Create transcription processor instance.

        Args:
            transcription_client: Transcription client instance
            text_inserter: Text inserter instance
            status_indicator: Optional desktop status indicator

        Returns:
            TranscriptionProcessor instance
        """
        return TranscriptionProcessor(transcription_client, text_inserter, status_indicator)
