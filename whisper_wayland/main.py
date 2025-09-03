"""
Whisper Wayland - Main Entry Point

A push-to-talk voice transcription service that converts speech to text
and inserts it at the cursor position in any application.
"""

import logging
import os
import signal
import sys
import threading
import time
import typing

import whisper_wayland.audio_recorder as audio_recorder
import whisper_wayland.config as config
import whisper_wayland.constants as constants
import whisper_wayland.key_monitor as key_monitor
import whisper_wayland.logging_config as logging_config
import whisper_wayland.text_inserter as text_inserter
import whisper_wayland.transcription_client as transcription_client

logger = logging.getLogger(__name__)


class WhisperClaudeApp:
    """Main application class for Whisper Claude service.

    Handles Step 3 functionality: real-time global hotkey detection with
    push-to-talk audio recording and transcription with cursor position
    text insertion.
    """

    def __init__(self, config_file: typing.Optional[str] = None) -> None:
        """Initialize the application.

        Args:
            config_file: Optional path to configuration file
        """
        self.config: typing.Optional[config.Config] = None
        self.audio_recorder: typing.Optional[audio_recorder.AudioRecorder] = None
        self.transcription_client: typing.Optional[transcription_client.TranscriptionClient] = None
        self.key_monitor: typing.Optional[key_monitor.KeyMonitor] = None
        self.text_inserter: typing.Optional[text_inserter.TextInserter] = None
        self._running = False
        self._recording_active = False

        try:
            self._initialize(config_file)
            logger.info("Whisper Claude application initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
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
        self.audio_recorder = audio_recorder.create_audio_recorder(self.config)

        # Initialize transcription client
        self.transcription_client = transcription_client.create_transcription_client(self.config)

        # Initialize key monitor
        self.key_monitor = key_monitor.create_key_monitor(self.config)

        # Initialize text inserter
        self.text_inserter = text_inserter.create_text_inserter(self.config)

        # Test API connection
        logger.info("Testing OpenAI API connection...")
        if not self.transcription_client.test_connection():
            logger.warning("OpenAI API connection test failed, but continuing...")

        # Test text insertion capability
        logger.info("Testing text insertion capability...")
        if not self.text_inserter.test_insertion():
            logger.warning("Text insertion test failed, but continuing...")

    def run(self) -> None:
        """Run the main application loop for Step 3.

        Provides real-time global hotkey detection with push-to-talk recording
        and transcription with cursor position text insertion.
        """
        if not self._validate_components():
            logger.error("Cannot start application - component validation failed")
            return

        logger.info("Starting Whisper Claude service (Step 3: Text insertion at cursor)")
        logger.info("Usage:")
        if self.config:
            logger.info(f"  - Press and hold {self.config.hotkey} to record audio")
        logger.info("  - Release to stop recording and transcribe")
        logger.info("  - Transcribed text will be inserted at cursor position")
        logger.info("  - Press Ctrl+C to exit")

        # Log available text insertion methods
        if self.text_inserter:
            available_methods = self.text_inserter.get_available_methods()
            preferred_method = self.text_inserter.get_preferred_method()
            logger.info(f"  - Text insertion method: {preferred_method}")
            logger.debug(f"  - Available methods: {available_methods}")

        self._setup_signal_handlers()
        self._setup_hotkey_callbacks()
        self._running = True

        try:
            self._main_loop()
        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Application error: {e}")
        finally:
            self.cleanup()

    def _validate_components(self) -> bool:
        """Validate that all required components are initialized.

        Returns:
            True if all components are valid, False otherwise
        """
        if not self.config:
            logger.error("Configuration not initialized")
            return False

        if not self.audio_recorder:
            logger.error("Audio recorder not initialized")
            return False

        if not self.transcription_client:
            logger.error("Transcription client not initialized")
            return False

        if not self.key_monitor:
            logger.error("Key monitor not initialized")
            return False

        if not self.text_inserter:
            logger.error("Text inserter not initialized")
            return False

        return True

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: typing.Any) -> None:
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self._running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _setup_hotkey_callbacks(self) -> None:
        """Setup hotkey press and release callbacks."""
        if not self.key_monitor:
            logger.error("Key monitor not available for callback setup")
            return

        # Set callback for hotkey press (start recording)
        self.key_monitor.set_callback(self._on_hotkey_press)

        # Set callback for hotkey release (stop recording)
        self.key_monitor.set_release_callback(self._on_hotkey_release)

        logger.debug("Hotkey callbacks configured")

    def _on_hotkey_press(self) -> None:
        """Handle hotkey press event - start recording."""
        if self._recording_active:
            logger.debug("Recording already active, ignoring hotkey press")
            return

        logger.info("Hotkey pressed - starting recording")
        self._recording_active = True

        try:
            if self.audio_recorder:
                self.audio_recorder.start_recording()
        except audio_recorder.AudioRecordingError as e:
            logger.error(f"Failed to start recording: {e}")
            self._recording_active = False

    def _on_hotkey_release(self) -> None:
        """Handle hotkey release event - stop recording and transcribe."""
        if not self._recording_active:
            logger.debug("Recording not active, ignoring hotkey release")
            return

        logger.info("Hotkey released - stopping recording")
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
                    logger.warning("No audio data captured")
        except audio_recorder.AudioRecordingError as e:
            logger.error(f"Failed to stop recording: {e}")

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
                logger.info("No transcription result")
        except Exception as e:
            logger.error(f"Error processing transcription: {e}")

    def _main_loop(self) -> None:
        """Main application loop for Step 2 functionality."""
        if self.config:
            logger.info(f"Application ready - waiting for {self.config.hotkey}...")
        else:
            logger.info("Application ready - waiting for hotkey...")

        # Start key monitoring
        try:
            if self.key_monitor:
                self.key_monitor.start_monitoring()
                logger.info("Global hotkey monitoring active")
        except key_monitor.KeyMonitorError as e:
            logger.error(f"Failed to start key monitoring: {e}")
            return

        # Keep application running while monitoring hotkeys
        try:
            while self._running:
                time.sleep(0.1)  # Small sleep to prevent busy waiting
        except Exception as e:
            logger.error(f"Error in main loop: {e}")

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
            logger.error("Audio recorder not available")
            return None

        try:
            logger.info("Starting audio recording... (speak now)")
            self.audio_recorder.start_recording()

            # Simple Step 1 implementation: record for fixed time or until Enter
            print("Recording... Press Enter to stop recording")
            try:
                input()
            except (EOFError, KeyboardInterrupt):
                pass

            logger.info("Stopping audio recording...")
            audio_data = self.audio_recorder.stop_recording()

            if audio_data:
                logger.info(f"Audio recording completed: {len(audio_data)} bytes")
            else:
                logger.warning("No audio data captured")

            return audio_data

        except audio_recorder.AudioRecordingError as e:
            logger.error(f"Audio recording error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during recording: {e}")
            return None

    def _transcribe_audio(self, audio_data: bytes) -> typing.Optional[str]:
        """Transcribe audio data to text.

        Args:
            audio_data: Raw audio data

        Returns:
            Transcribed text or None if transcription failed
        """
        if not self.transcription_client:
            logger.error("Transcription client not available")
            return None

        try:
            logger.info("Starting audio transcription...")
            transcribed_text = self.transcription_client.transcribe_audio(audio_data)

            if transcribed_text:
                preview_len = constants.TRANSCRIPTION_PREVIEW_LENGTH
                preview_text = transcribed_text[:preview_len]
                ellipsis = "..." if len(transcribed_text) > preview_len else ""
                logger.info(f"Transcription completed: '{preview_text}{ellipsis}'")
            else:
                logger.warning("Transcription returned empty result")

            return transcribed_text

        except transcription_client.TranscriptionError as e:
            logger.error(f"Transcription error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {e}")
            return None

    def _insert_text(self, text: str) -> None:
        """Insert transcribed text at cursor position.

        Args:
            text: Transcribed text to insert
        """
        if not self.text_inserter:
            logger.error("Text inserter not available")
            print("Text insertion failed - inserter not available")
            print(f"Transcribed text: {text}")
            return

        try:
            preview_len = constants.TEXT_PREVIEW_LENGTH
            preview_text = text[:preview_len]
            ellipsis = "..." if len(text) > preview_len else ""
            logger.info(f"Inserting transcribed text: '{preview_text}{ellipsis}'")
            success = self.text_inserter.insert_text(text)

            if success:
                logger.info("Text insertion successful")
                print(f"✓ Inserted: {text}")
            else:
                logger.error("Text insertion failed")
                print(f"✗ Failed to insert text: {text}")
                print("Check that you have focus on a text input field")

        except text_inserter.TextInsertionError as e:
            logger.error(f"Text insertion error: {e}")
            print(f"Text insertion error: {e}")
            print(f"Transcribed text: {text}")
        except Exception as e:
            logger.error(f"Unexpected error during text insertion: {e}")
            print(f"Unexpected error during text insertion: {e}")
            print(f"Transcribed text: {text}")

    def cleanup(self) -> None:
        """Clean up application resources."""
        logger.info("Cleaning up application resources...")

        try:
            if self.key_monitor:
                self.key_monitor.close()

            if self.audio_recorder:
                self.audio_recorder.close()

            if self.transcription_client:
                self.transcription_client.close()

            if self.text_inserter:
                self.text_inserter.close()

            logger.info("Application cleanup completed")

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main() -> None:
    """Main entry point for the application."""
    try:
        # Check for config file argument
        config_file = None
        if len(sys.argv) > 1:
            config_file = sys.argv[1]
            if not os.path.exists(config_file):
                print(f"Error: Configuration file '{config_file}' not found")
                sys.exit(1)

        # Create and run application
        app = WhisperClaudeApp(config_file)
        app.run()

    except config.ConfigError as e:
        print(f"Configuration error: {e}")
        print("Please check your environment variables or .env file")
        sys.exit(1)
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
