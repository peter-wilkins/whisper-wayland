"""Whisper Wayland - Hotkey Handler

Manages hotkey press/release events and coordinates with audio recording.
"""

import logging
import threading
import typing

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class HotkeyHandler:
    """Handles hotkey events for push-to-talk functionality."""

    def __init__(
        self,
        audio_recorder: "ww.AudioRecorder",
        transcription_processor: typing.Any,  # Forward reference to avoid circular import
        mode: str = "push_to_talk",
    ) -> None:
        """Initialize hotkey handler.

        Args:
            audio_recorder: Audio recorder instance
            transcription_processor: Transcription processor instance
            mode: Hotkey activation mode
        """
        self.audio_recorder = audio_recorder
        self.transcription_processor = transcription_processor
        self.mode = mode
        self._recording_active = False

    def setup_callbacks(self, key_monitor: "ww.KeyMonitor") -> None:
        """Setup hotkey press and release callbacks.

        Args:
            key_monitor: Key monitor instance to configure
        """
        # Set callback for hotkey press (start recording or toggle)
        key_monitor.set_callback(self._on_hotkey_press)

        if self.mode == "push_to_talk":
            # Set callback for hotkey release (stop recording)
            key_monitor.set_release_callback(self._on_hotkey_release)

        _logger.debug("Hotkey callbacks configured")

    def _on_hotkey_press(self) -> None:
        """Handle hotkey press event - start recording."""
        if self.mode == "toggle" and self._recording_active:
            self._on_hotkey_release()
            return

        if self._recording_active:
            _logger.debug("Recording already active, ignoring hotkey press")
            return

        _logger.info("Hotkey pressed - starting recording")
        self._recording_active = True

        try:
            self.audio_recorder.start_recording()
        except ww.AudioRecordingError as e:
            _logger.error(f"Failed to start recording: {e}")
            self._recording_active = False

    def _on_hotkey_release(self) -> None:
        """Handle hotkey release event - stop recording and transcribe."""
        if not self._recording_active:
            _logger.debug("Recording not active, ignoring hotkey release")
            return

        _logger.info("Hotkey released - stopping recording")
        self._recording_active = False

        try:
            audio_data = self.audio_recorder.stop_recording()

            if audio_data:
                # Process transcription in background
                threading.Thread(
                    target=self.transcription_processor.process_audio,
                    args=(audio_data,),
                    daemon=True,
                ).start()
            else:
                _logger.warning("No audio data captured")
        except ww.AudioRecordingError as e:
            _logger.error(f"Failed to stop recording: {e}")

    @property
    def is_recording_active(self) -> bool:
        """Check if recording is currently active.

        Returns:
            True if recording is active, False otherwise
        """
        return self._recording_active

    @staticmethod
    def new(
        audio_recorder: "ww.AudioRecorder",
        transcription_processor: typing.Any,  # Forward reference
        mode: str = "push_to_talk",
    ) -> "HotkeyHandler":
        """Create hotkey handler instance.

        Args:
            audio_recorder: Audio recorder instance
            transcription_processor: Transcription processor instance
            mode: Hotkey activation mode

        Returns:
            HotkeyHandler instance
        """
        return HotkeyHandler(audio_recorder, transcription_processor, mode)
