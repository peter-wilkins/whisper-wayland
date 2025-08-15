"""Main entry point for Whisper Claude service.

Provides the main application logic for Step 2: real-time global hotkey
detection with push-to-talk recording and transcription to file output.
"""

import logging
import os
import signal
import sys
import threading
import time
from typing import Any, Optional

from .audio_recorder import AudioRecorder, AudioRecordingError, create_audio_recorder
from .config import Config, ConfigError, get_config
from .key_monitor import KeyMonitor, KeyMonitorError, create_key_monitor
from .logging_config import setup_logging
from .transcription_client import (
    TranscriptionClient,
    TranscriptionError,
    create_transcription_client,
)

logger = logging.getLogger(__name__)


class WhisperClaudeApp:
    """Main application class for Whisper Claude service.

    Handles Step 2 functionality: real-time global hotkey detection with
    push-to-talk audio recording and transcription to file output.
    """

    def __init__(self, config_file: Optional[str] = None) -> None:
        """Initialize the application.

        Args:
            config_file: Optional path to configuration file
        """
        self.config: Optional[Config] = None
        self.audio_recorder: Optional[AudioRecorder] = None
        self.transcription_client: Optional[TranscriptionClient] = None
        self.key_monitor: Optional[KeyMonitor] = None
        self._running = False
        self._transcription_file = "transcription.txt"
        self._recording_active = False

        try:
            self._initialize(config_file)
            logger.info("Whisper Claude application initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize application: {e}")
            raise

    def _initialize(self, config_file: Optional[str]) -> None:
        """Initialize application components.

        Args:
            config_file: Optional path to configuration file
        """
        # Load configuration
        self.config = get_config(config_file)

        # Setup logging
        setup_logging(self.config)

        # Initialize audio recorder
        self.audio_recorder = create_audio_recorder(self.config)

        # Initialize transcription client
        self.transcription_client = create_transcription_client(self.config)

        # Initialize key monitor
        self.key_monitor = create_key_monitor(self.config)

        # Test API connection
        logger.info("Testing OpenAI API connection...")
        if not self.transcription_client.test_connection():
            logger.warning("OpenAI API connection test failed, but continuing...")

    def run(self) -> None:
        """Run the main application loop for Step 2.

        Provides real-time global hotkey detection with push-to-talk recording
        and transcription to file output.
        """
        if not self._validate_components():
            logger.error("Cannot start application - component validation failed")
            return

        logger.info("Starting Whisper Claude service (Step 2: Push-to-talk hotkey)")
        logger.info("Usage:")
        if self.config:
            logger.info(f"  - Press and hold {self.config.hotkey} to record audio")
        logger.info("  - Release to stop recording and transcribe")
        logger.info("  - Transcribed text will be saved to transcription.txt")
        logger.info("  - Press Ctrl+C to exit")

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

        return True

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame: Any) -> None:
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
        except AudioRecordingError as e:
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
        except AudioRecordingError as e:
            logger.error(f"Failed to stop recording: {e}")

    def _process_transcription(self, audio_data: bytes) -> None:
        """Process transcription in background thread.

        Args:
            audio_data: Audio data to transcribe
        """
        try:
            transcribed_text = self._transcribe_audio(audio_data)

            if transcribed_text:
                self._save_transcription(transcribed_text)
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
        except KeyMonitorError as e:
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
        print(
            "\nPress Enter to simulate Ctrl+Space recording trigger (or Ctrl+C to exit)..."
        )
        try:
            input()
        except (EOFError, KeyboardInterrupt):
            self._running = False

    def _record_audio_session(self) -> Optional[bytes]:
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

        except AudioRecordingError as e:
            logger.error(f"Audio recording error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during recording: {e}")
            return None

    def _transcribe_audio(self, audio_data: bytes) -> Optional[str]:
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
                logger.info(
                    f"Transcription completed: '{transcribed_text[:100]}{'...' if len(transcribed_text) > 100 else ''}'"
                )
            else:
                logger.warning("Transcription returned empty result")

            return transcribed_text

        except TranscriptionError as e:
            logger.error(f"Transcription error: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error during transcription: {e}")
            return None

    def _save_transcription(self, text: str) -> None:
        """Save transcribed text to file.

        Args:
            text: Transcribed text to save
        """
        try:
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

            # Append to transcription file
            with open(self._transcription_file, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] {text}\n")

            logger.info(f"Transcription saved to {self._transcription_file}")
            print(f"Transcribed text: {text}")
            print(f"Saved to: {self._transcription_file}")

        except Exception as e:
            logger.error(f"Failed to save transcription: {e}")
            print(f"Failed to save transcription: {e}")
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

    except ConfigError as e:
        print(f"Configuration error: {e}")
        print("Please check your environment variables or .env file")
        sys.exit(1)
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
