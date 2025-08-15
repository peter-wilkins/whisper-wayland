"""Main entry point for Whisper Claude service.

Provides the main application logic for Step 1: basic audio recording
and transcription to file with Ctrl+Space hotkey functionality.
"""

import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional

from .config import Config, get_config, ConfigError
from .logging_config import setup_logging
from .audio_recorder import AudioRecorder, create_audio_recorder, AudioRecordingError
from .transcription_client import (
    TranscriptionClient,
    create_transcription_client,
    TranscriptionError,
)

logger = logging.getLogger(__name__)


class WhisperClaudeApp:
    """Main application class for Whisper Claude service.

    Handles the Step 1 functionality: audio recording with Ctrl+Space
    and transcription to file output.
    """

    def __init__(self, config_file: Optional[str] = None) -> None:
        """Initialize the application.

        Args:
            config_file: Optional path to configuration file
        """
        self.config: Optional[Config] = None
        self.audio_recorder: Optional[AudioRecorder] = None
        self.transcription_client: Optional[TranscriptionClient] = None
        self._running = False
        self._transcription_file = "transcription.txt"

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

        # Test API connection
        logger.info("Testing OpenAI API connection...")
        if not self.transcription_client.test_connection():
            logger.warning("OpenAI API connection test failed, but continuing...")

    def run(self) -> None:
        """Run the main application loop for Step 1.

        Provides simple Ctrl+Space recording functionality with file output.
        """
        if not self._validate_components():
            logger.error("Cannot start application - component validation failed")
            return

        logger.info("Starting Whisper Claude service (Step 1: Basic transcription)")
        logger.info("Usage:")
        logger.info("  - Press and hold Ctrl+Space to record audio")
        logger.info("  - Release to stop recording and transcribe")
        logger.info("  - Transcribed text will be saved to transcription.txt")
        logger.info("  - Press Ctrl+C to exit")

        self._setup_signal_handlers()
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

        return True

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""
        
        def signal_handler(signum: int, frame) -> None:
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self._running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def _main_loop(self) -> None:
        """Main application loop for Step 1 functionality."""
        logger.info("Application ready - waiting for Ctrl+Space...")

        while self._running:
            try:
                # Simple implementation for Step 1: wait for user input
                # In Step 2, this will be replaced with proper hotkey detection
                self._wait_for_recording_trigger()

                if not self._running:
                    break

                # Record audio
                audio_data = self._record_audio_session()

                if audio_data:
                    # Transcribe audio
                    transcribed_text = self._transcribe_audio(audio_data)

                    if transcribed_text:
                        # Save to file
                        self._save_transcription(transcribed_text)
                    else:
                        logger.warning("No transcription result received")
                else:
                    logger.warning("No audio data recorded")

                logger.info("Ready for next recording (Ctrl+Space)...")

            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(1)  # Brief pause before continuing

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
                logger.info(f"Transcription completed: '{transcribed_text[:100]}{'...' if len(transcribed_text) > 100 else ''}'")
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