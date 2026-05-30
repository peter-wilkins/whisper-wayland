"""Whisper Wayland - Hotkey Handler

Manages hotkey press/release events and coordinates with audio recording.
"""

import logging
import threading
import time
import typing

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class HotkeyHandler:
    """Handles hotkey events for push-to-talk functionality."""

    MIN_HOLD_TO_TRANSCRIBE_SECS = 0.25

    def __init__(
        self,
        audio_recorder: "ww.AudioRecorder",
        transcription_processor: typing.Any,  # Forward reference to avoid circular import
        mode: str = "push_to_talk",
        status_indicator: typing.Any = None,
    ) -> None:
        """Initialize hotkey handler.

        Args:
            audio_recorder: Audio recorder instance
            transcription_processor: Transcription processor instance
            mode: Hotkey activation mode
            status_indicator: Optional desktop status indicator
        """
        self.audio_recorder = audio_recorder
        self.transcription_processor = transcription_processor
        self.mode = mode
        self.status_indicator = status_indicator
        self._recording_active = False
        self._streaming_active = False
        self._transcribing_active = False
        self._recording_started_at = 0.0
        self._recording_insertion_target: str | None = None
        self._state_lock = threading.Lock()

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
        with self._state_lock:
            if self.mode == "toggle" and self._recording_active:
                should_release = True
            else:
                should_release = False

            if not should_release and self._transcribing_active:
                _logger.info("Transcription already in progress, ignoring hotkey press")
                return

            if not should_release and self._recording_active:
                _logger.debug("Recording already active, ignoring hotkey press")
                return

            if not should_release:
                self._recording_active = True
                self._recording_started_at = time.monotonic()
                self._recording_insertion_target = self._capture_insertion_target()

        if should_release:
            self._on_hotkey_release()
            return

        _logger.info("Hotkey pressed - starting recording")

        try:
            if self._start_streaming_if_available():
                self._show_recording()
                return

            self.audio_recorder.refresh_input_device()
            self.audio_recorder.start_recording()
            self._show_recording()
        except ww.AudioRecordingError as e:
            _logger.error(f"Failed to start recording: {e}")
            with self._state_lock:
                self._recording_active = False
            self._show_error("Recording failed")

    def _on_hotkey_release(self) -> None:
        """Handle hotkey release event - stop recording and transcribe."""
        with self._state_lock:
            if not self._recording_active:
                _logger.debug("Recording not active, ignoring hotkey release")
                return

            self._recording_active = False
            self._transcribing_active = True
            recording_duration = time.monotonic() - self._recording_started_at
            insertion_target = self._recording_insertion_target
            self._recording_insertion_target = None

        _logger.info("Hotkey released - stopping recording")

        if recording_duration < self.MIN_HOLD_TO_TRANSCRIBE_SECS:
            _logger.info(
                "Ignoring %.0fms hotkey tap below %.0fms minimum hold",
                recording_duration * 1000,
                self.MIN_HOLD_TO_TRANSCRIBE_SECS * 1000,
            )
            self._cancel_recording()
            return

        self._show_transcribing()

        try:
            if self._streaming_active:
                self._streaming_active = False
                threading.Thread(
                    target=self._run_transcription_task,
                    args=(self.transcription_processor.stop_streaming, insertion_target),
                    daemon=True,
                ).start()
                return

            audio_source = self.audio_recorder.get_active_input_source()
            audio_data = self.audio_recorder.stop_recording()

            if audio_data:
                # Process transcription in background
                threading.Thread(
                    target=self._run_transcription_task,
                    args=(
                        self.transcription_processor.process_audio,
                        audio_data,
                        audio_source,
                        insertion_target,
                    ),
                    daemon=True,
                ).start()
            else:
                _logger.warning("No audio data captured")
                with self._state_lock:
                    self._transcribing_active = False
                self._show_error("No audio captured")
        except ww.AudioRecordingError as e:
            _logger.error(f"Failed to stop recording: {e}")
            with self._state_lock:
                self._transcribing_active = False
            self._show_error("Recording failed")

    def _cancel_recording(self) -> None:
        """Cancel a jitter tap without starting transcription."""
        try:
            if self._streaming_active:
                self._streaming_active = False
                cancel_streaming = getattr(self.transcription_processor, "cancel_streaming", None)
                if cancel_streaming:
                    cancel_streaming()
                return

            self.audio_recorder.stop_recording()
        except Exception as e:
            _logger.debug(f"Error cancelling short recording: {e}")
        finally:
            with self._state_lock:
                self._transcribing_active = False
                self._recording_insertion_target = None
            self._show_idle()

    def _run_transcription_task(
        self,
        task: typing.Callable[..., None],
        *args: typing.Any,
    ) -> None:
        """Run transcription work and mark the handler idle when it finishes."""
        try:
            task(*args)
        finally:
            with self._state_lock:
                self._transcribing_active = False

    def _start_streaming_if_available(self) -> bool:
        """Attempt realtime streaming if the transcription processor supports it."""
        if getattr(self.transcription_processor, "streaming_enabled", False) is not True:
            return False

        if self.transcription_processor.start_streaming():
            self._streaming_active = True
            return True

        _logger.warning("Realtime streaming unavailable; falling back to batch recording")
        return False

    def _capture_insertion_target(self) -> str | None:
        """Capture the text insertion destination at recording start, if supported."""
        capture = getattr(self.transcription_processor, "capture_insertion_target", None)
        if not callable(capture):
            return None

        try:
            target = capture()
        except Exception as e:
            _logger.debug("Could not capture insertion target: %s", e)
            return None

        return target if isinstance(target, str) and target else None

    def _show_recording(self) -> None:
        """Update indicator to recording state."""
        if self.status_indicator:
            self.status_indicator.recording()

    def _show_transcribing(self) -> None:
        """Update indicator to transcription state."""
        if self.status_indicator:
            self.status_indicator.transcribing()

    def _show_error(self, message: str) -> None:
        """Update indicator to error state."""
        if self.status_indicator:
            self.status_indicator.error(message)

    def _show_idle(self) -> None:
        """Update indicator to idle state."""
        if self.status_indicator:
            self.status_indicator.idle()

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
        status_indicator: typing.Any = None,
    ) -> "HotkeyHandler":
        """Create hotkey handler instance.

        Args:
            audio_recorder: Audio recorder instance
            transcription_processor: Transcription processor instance
            mode: Hotkey activation mode
            status_indicator: Optional desktop status indicator

        Returns:
            HotkeyHandler instance
        """
        return HotkeyHandler(audio_recorder, transcription_processor, mode, status_indicator)
