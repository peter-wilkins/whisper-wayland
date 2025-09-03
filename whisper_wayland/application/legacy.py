"""Whisper Wayland - Legacy Simple Recording Functionality

Provides backward compatibility for simple recording mode.
"""

import logging
import typing

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class LegacyRecorder:
    """Legacy simple recording functionality."""

    def __init__(self, audio_recorder: "ww.AudioRecorder") -> None:
        """Initialize legacy recorder.

        Args:
            audio_recorder: Audio recorder instance
        """
        self.audio_recorder = audio_recorder

    def wait_for_recording_trigger(self) -> bool:
        """Wait for recording trigger (simple implementation).

        This is a simple prompt for demonstration purposes.

        Returns:
            True to continue, False to exit
        """
        # Simple implementation: wait for Enter key
        print("\nPress Enter to simulate Ctrl+Space recording trigger (or Ctrl+C to exit)...")
        try:
            input()
            return True
        except (EOFError, KeyboardInterrupt):
            return False

    def record_audio_session(self) -> typing.Optional[bytes]:
        """Record an audio session (simple functionality).

        Returns:
            Recorded audio data or None if recording failed
        """
        try:
            _logger.info("Starting audio recording... (speak now)")
            self.audio_recorder.start_recording()

            # Simple implementation: record for fixed time or until Enter
            print("Recording... Press Enter to stop recording")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass

            _logger.info("Stopping audio recording...")
            audio_data = self.audio_recorder.stop_recording()

            if audio_data:
                _logger.info(f"Audio recording completed: {len(audio_data)} bytes")
            else:
                _logger.warning("No audio data captured")

            return audio_data

        except ww.AudioRecordingError as e:
            _logger.error(f"Audio recording error: {e}")
            return None
        except Exception as e:
            _logger.error(f"Unexpected error during recording: {e}")
            return None

    @staticmethod
    def new(audio_recorder: "ww.AudioRecorder") -> "LegacyRecorder":
        """Create legacy recorder instance.

        Args:
            audio_recorder: Audio recorder instance

        Returns:
            LegacyRecorder instance
        """
        return LegacyRecorder(audio_recorder)
