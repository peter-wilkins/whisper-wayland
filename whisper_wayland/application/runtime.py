"""Whisper Wayland - Runtime Management

Handles application runtime, main loop, and signal management.
"""

import logging
import signal
import time
import typing

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class RuntimeManager:
    """Manages application runtime and lifecycle."""

    def __init__(self, app_instance: typing.Any) -> None:  # Forward reference
        """Initialize runtime manager.

        Args:
            app_instance: Application instance
        """
        self.app = app_instance

    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: typing.Any) -> None:
            _logger.info(f"Received signal {signum}, initiating shutdown...")
            self.app._running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def setup_hotkey_monitoring(self) -> None:
        """Setup hotkey monitoring and callbacks."""
        if not self.app.component_manager or not self.app.component_manager.key_monitor:
            _logger.error("Key monitor not available")
            return

        if not self.app.hotkey_handler:
            _logger.error("Hotkey handler not available")
            return

        # Setup callbacks
        self.app.hotkey_handler.setup_callbacks(self.app.component_manager.key_monitor)

        # Start key monitoring
        try:
            self.app.component_manager.key_monitor.start_monitoring()
            _logger.info("Global hotkey monitoring active")
        except ww.KeyMonitorError as e:
            _logger.error(f"Failed to start key monitoring: {e}")
            raise

    def run_main_loop(self) -> None:
        """Run the main application loop."""
        if self.app.config:
            _logger.info(f"Application ready - waiting for {self.app.config.hotkey}...")
        else:
            _logger.info("Application ready - waiting for hotkey...")

        # Keep application running while monitoring hotkeys
        try:
            while self.app._running:
                time.sleep(0.1)  # Small sleep to prevent busy waiting
        except Exception as e:
            _logger.error(f"Error in main loop: {e}")

    def wait_for_recording_trigger(self) -> None:
        """Wait for recording trigger (Step 1: simple implementation).

        In Step 1, this is a simple prompt for demonstration.
        In Step 2, this will be replaced with proper hotkey detection.
        """
        # Simple Step 1 implementation: wait for Enter key
        print("\nPress Enter to simulate Ctrl+Space recording trigger (or Ctrl+C to exit)...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            self.app._running = False

    def record_audio_session(self) -> bytes | None:
        """Record an audio session (Step 1 functionality).

        Returns:
            Recorded audio data or None if recording failed
        """
        if not self.app.component_manager or not self.app.component_manager.audio_recorder:
            _logger.error("Audio recorder not available")
            return None

        try:
            _logger.info("Starting audio recording... (speak now)")
            self.app.component_manager.audio_recorder.start_recording()

            # Simple Step 1 implementation: record for fixed time or until Enter
            print("Recording... Press Enter to stop recording")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass

            _logger.info("Stopping audio recording...")
            audio_data: bytes | None = self.app.component_manager.audio_recorder.stop_recording()

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
