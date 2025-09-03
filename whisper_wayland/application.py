"""Whisper Wayland - Application

Main application class for Whisper Wayland service with real-time global
hotkey detection, push-to-talk audio recording, and text insertion.
"""

import logging
import signal
import threading
import time
import typing

import whisper_wayland as ww
import whisper_wayland.config as config
import whisper_wayland.constants as constants
import whisper_wayland.logging_config as logging_config

_logger = logging.getLogger(__name__)


class Application:
    """Main application class for Whisper Wayland service.

    Real-time global hotkey detection with
    push-to-talk audio recording and transcription
    with cursor position text insertion.
    """

    def __init__(self, config_file: typing.Optional[str] = None) -> None:
        """Initialize the application.

        Args:
            config_file: Optional path to configuration file
        """
        self.config: typing.Optional[config.Config] = None
        self.audio_recorder: typing.Optional[ww.AudioRecorder] = None
        self.transcription_client: typing.Optional[ww.TranscriptionClient] = None
        self.key_monitor: typing.Optional[ww.KeyMonitor] = None
        self.text_inserter: typing.Optional[ww.TextInserter] = None
        self._running = False
        self._recording_active = False

        try:
            self._initialize(config_file)
            _logger.info("Whisper Wayland application initialized successfully")
        except Exception as e:
            _logger.error(f"Failed to initialize application: {e}")
            raise

    def _initialize(self, config_file: typing.Optional[str]) -> None:
        """Initialize application components.

        Args:
            config_file: Optional path to configuration file
        """
        # Load configuration
        self.config = config.get_config(config_file)

        # Setup logging
        logging_config.setup_logging(self.config)

        # Initialize audio recorder
        self.audio_recorder = ww.AudioRecorder.new(self.config)

        # Initialize transcription client
        self.transcription_client = ww.TranscriptionClient.new(self.config)

        # Initialize key monitor
        self.key_monitor = ww.KeyMonitor.new(self.config)

        # Initialize text inserter
        self.text_inserter = ww.TextInserter.new(self.config)

        # Test API connection
        _logger.info("Testing OpenAI API connection...")
        if not self.transcription_client.test_connection():
            _logger.warning("OpenAI API connection test failed, but continuing...")

        # Test text insertion capability
        _logger.info("Testing text insertion capability...")
        if not self.text_inserter.test_insertion():
            _logger.warning("Text insertion test failed, but continuing...")

    def run(self) -> None:
        """Run the main application loop.

        Provides real-time global hotkey detection with push-to-talk recording
        and transcription with cursor position text insertion.
        """
        if not self._validate_components():
            _logger.error("Cannot start application - component validation failed")
            return

        _logger.info("Starting Whisper Wayland service (Step 3: Text insertion at cursor)")
        _logger.info("Usage:")
        if self.config:
            _logger.info(f"  - Press and hold {self.config.hotkey} to record audio")
        _logger.info("  - Release to stop recording and transcribe")
        _logger.info("  - Transcribed text will be inserted at cursor position")
        _logger.info("  - Press Ctrl+C to exit")

        # Log available text insertion methods
        if self.text_inserter:
            available_methods = self.text_inserter.get_available_methods()
            preferred_method = self.text_inserter.get_preferred_method()
            _logger.info(f"  - Text insertion method: {preferred_method}")
            _logger.debug(f"  - Available methods: {available_methods}")

        self._setup_signal_handlers()
        self._setup_hotkey_callbacks()
        self._running = True

        try:
            self._main_loop()
        except KeyboardInterrupt:
            _logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            _logger.error(f"Application error: {e}")
        finally:
            self.cleanup()

    def _validate_components(self) -> bool:
        """Validate that all required components are initialized.

        Returns:
            True if all components are valid, False otherwise
        """
        if not self.config:
            _logger.error("Configuration not initialized")
            return False

        if not self.audio_recorder:
            _logger.error("Audio recorder not initialized")
            return False

        if not self.transcription_client:
            _logger.error("Transcription client not initialized")
            return False

        if not self.key_monitor:
            _logger.error("Key monitor not initialized")
            return False

        if not self.text_inserter:
            _logger.error("Text inserter not initialized")
            return False

        return True

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: typing.Any) -> None:
            _logger.info(f"Received signal {signum}, initiating shutdown...")
            self._running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _setup_hotkey_callbacks(self) -> None:
        """Setup hotkey press and release callbacks."""
        if not self.key_monitor:
            _logger.error("Key monitor not available for callback setup")
            return

        # Set callback for hotkey press (start recording)
        self.key_monitor.set_callback(self._on_hotkey_press)

        # Set callback for hotkey release (stop recording)
        self.key_monitor.set_release_callback(self._on_hotkey_release)

        _logger.debug("Hotkey callbacks configured")

    def _on_hotkey_press(self) -> None:
        """Handle hotkey press event - start recording."""
        if self._recording_active:
            _logger.debug("Recording already active, ignoring hotkey press")
            return

        _logger.info("Hotkey pressed - starting recording")
        self._recording_active = True

        try:
            if self.audio_recorder:
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
            if self.audio_recorder:
                audio_data = self.audio_recorder.stop_recording()

                if audio_data:
                    # Process transcription in background
                    threading.Thread(
                        target=self._process_transcription,
                        args=(audio_data,),
                        daemon=True,
                    ).start()
                else:
                    _logger.warning("No audio data captured")
        except ww.AudioRecordingError as e:
            _logger.error(f"Failed to stop recording: {e}")

    def _process_transcription(self, audio_data: bytes) -> None:
        """Process transcription in background thread.

        Args:
            audio_data: Audio data to transcribe
        """
        try:
            transcribed_text = self._transcribe_audio(audio_data)

            if transcribed_text:
                self._insert_text(transcribed_text)
            else:
                _logger.info("No transcription result")
        except Exception as e:
            _logger.error(f"Error processing transcription: {e}")

    def _main_loop(self) -> None:
        """Main application loop for Step 2 functionality."""
        if self.config:
            _logger.info(f"Application ready - waiting for {self.config.hotkey}...")
        else:
            _logger.info("Application ready - waiting for hotkey...")

        # Start key monitoring
        try:
            if self.key_monitor:
                self.key_monitor.start_monitoring()
                _logger.info("Global hotkey monitoring active")
        except ww.KeyMonitorError as e:
            _logger.error(f"Failed to start key monitoring: {e}")
            return

        # Keep application running while monitoring hotkeys
        try:
            while self._running:
                time.sleep(0.1)  # Small sleep to prevent busy waiting
        except Exception as e:
            _logger.error(f"Error in main loop: {e}")

    def _wait_for_recording_trigger(self) -> None:
        """Wait for recording trigger (Step 1: simple implementation).

        In Step 1, this is a simple prompt for demonstration.
        In Step 2, this will be replaced with proper hotkey detection.
        """
        # Simple Step 1 implementation: wait for Enter key
        print("\nPress Enter to simulate Ctrl+Space recording trigger (or Ctrl+C to exit)...")
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            self._running = False

    def _record_audio_session(self) -> typing.Optional[bytes]:
        """Record an audio session.

        Returns:
            Recorded audio data or None if recording failed
        """
        if not self.audio_recorder:
            _logger.error("Audio recorder not available")
            return None

        try:
            _logger.info("Starting audio recording... (speak now)")
            self.audio_recorder.start_recording()

            # Simple Step 1 implementation: record for fixed time or until Enter
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

    def _transcribe_audio(self, audio_data: bytes) -> typing.Optional[str]:
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio data

        Returns:
            Transcribed text or None if transcription failed
        """
        if not self.transcription_client:
            _logger.error("Transcription client not available")
            return None

        try:
            _logger.info("Starting audio transcription...")
            transcribed_text = self.transcription_client.transcribe_audio(audio_data)

            if transcribed_text:
                preview_len = constants.TRANSCRIPTION_PREVIEW_LENGTH
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

    def _insert_text(self, text: str) -> None:
        """Insert transcribed text at cursor position.

        Args:
            text: Transcribed text to insert
        """
        if not self.text_inserter:
            _logger.error("Text inserter not available")
            print("Text insertion failed - inserter not available")
            print(f"Transcribed text: {text}")
            return

        try:
            preview_len = constants.TEXT_PREVIEW_LENGTH
            preview_text = text[:preview_len]
            ellipsis = "..." if len(text) > preview_len else ""
            _logger.info(f"Inserting transcribed text: '{preview_text}{ellipsis}'")
            success = self.text_inserter.insert_text(text)

            if success:
                _logger.info("Text insertion successful")
                print(f"✓ Inserted: {text}")
            else:
                _logger.error("Text insertion failed")
                print(f"✗ Failed to insert text: {text}")
                print("Check that you have focus on a text input field")

        except ww.TextInsertionError as e:
            _logger.error(f"Text insertion error: {e}")
            print(f"Text insertion error: {e}")
            print(f"Transcribed text: {text}")
        except Exception as e:
            _logger.error(f"Unexpected error during text insertion: {e}")
            print(f"Unexpected error during text insertion: {e}")
            print(f"Transcribed text: {text}")

    def cleanup(self) -> None:
        """Clean up application resources."""
        _logger.info("Cleaning up application resources...")

        try:
            if self.key_monitor:
                self.key_monitor.close()

            if self.audio_recorder:
                self.audio_recorder.close()

            if self.transcription_client:
                self.transcription_client.close()

            if self.text_inserter:
                self.text_inserter.close()

            _logger.info("Application cleanup completed")

        except Exception as e:
            _logger.error(f"Error during cleanup: {e}")
