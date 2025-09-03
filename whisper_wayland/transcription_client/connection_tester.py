"""Whisper Wayland - Connection Tester

Tests OpenAI API connection with minimal requests.
"""

import logging
import typing

from whisper_wayland.transcription_client.test_audio_generator import TestAudioGenerator

_logger = logging.getLogger(__name__)


class ConnectionTester:
    """Tests OpenAI API connection functionality."""

    def __init__(self, transcription_engine: typing.Any) -> None:  # Forward reference
        """Initialize connection tester.

        Args:
            transcription_engine: Transcription engine instance
        """
        self._transcription_engine = transcription_engine
        self._test_audio_generator = TestAudioGenerator.new()

    def test_connection(self) -> bool:
        """Test connection to OpenAI API with a minimal request.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Create minimal test audio data (silence)
            test_audio_data = self._test_audio_generator.create_test_audio()
            result = self._transcription_engine.transcribe_audio(test_audio_data, max_retries=1)

            if result is not None:
                _logger.info("OpenAI API connection test successful")
                return True
            else:
                _logger.warning("OpenAI API connection test returned no result")
                return False

        except Exception as e:
            _logger.error(f"OpenAI API connection test failed: {e}")
            return False

    @staticmethod
    def new(transcription_engine: typing.Any) -> "ConnectionTester":
        """Create connection tester instance.

        Args:
            transcription_engine: Transcription engine instance

        Returns:
            ConnectionTester instance
        """
        return ConnectionTester(transcription_engine)
