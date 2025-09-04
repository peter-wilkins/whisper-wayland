"""Whisper Wayland - Application Orchestrator

Main application class that coordinates all components and manages the service lifecycle.
"""

import logging
import typing

import whisper_wayland as ww
from whisper_wayland.application.component_manager import ComponentManager
from whisper_wayland.application.hotkey_handler import HotkeyHandler
from whisper_wayland.application.runtime import RuntimeManager
from whisper_wayland.application.transcription_processor import TranscriptionProcessor

_logger = logging.getLogger(__name__)


class Application:
    """Main application class for Whisper Wayland service.

    Real-time global hotkey detection with push-to-talk audio recording
    and transcription with cursor position text insertion.
    """

    def __init__(self, config_file: typing.Optional[str] = None) -> None:
        """Initialize the application.

        Args:
            config_file: Optional path to configuration file
        """
        self.config: typing.Optional[ww.Config] = None
        self.component_manager: typing.Optional[ComponentManager] = None
        self.hotkey_handler: typing.Optional[HotkeyHandler] = None
        self.transcription_processor: typing.Optional[TranscriptionProcessor] = None
        self.runtime_manager: typing.Optional[RuntimeManager] = None
        self._running = False

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
        self.config = ww.Config.get(config_file)

        # Setup logging
        self.config.setup_logging()

        # Initialize component manager
        self.component_manager = ComponentManager.new(self.config)

        # Initialize transcription processor
        if self.component_manager.transcription_client and self.component_manager.text_inserter:
            self.transcription_processor = TranscriptionProcessor.new(
                self.component_manager.transcription_client,
                self.component_manager.text_inserter,
            )

        # Initialize hotkey handler
        if self.component_manager.audio_recorder and self.transcription_processor:
            self.hotkey_handler = HotkeyHandler.new(
                self.component_manager.audio_recorder,
                self.transcription_processor,
            )

        # Initialize runtime manager
        self.runtime_manager = RuntimeManager(self)

    def run(self) -> None:
        """Run the main application loop."""
        if not self.component_manager or not self.component_manager.validate_components():
            _logger.error("Cannot start application - component validation failed")
            return

        if not self.runtime_manager:
            _logger.error("Runtime manager not initialized")
            return

        self._log_startup_info()
        self.runtime_manager.setup_signal_handlers()
        self.runtime_manager.setup_hotkey_monitoring()
        self._running = True

        try:
            self.runtime_manager.run_main_loop()
        except KeyboardInterrupt:
            _logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            _logger.error(f"Application error: {e}")
        finally:
            self.cleanup()

    def _log_startup_info(self) -> None:
        """Log application startup information."""
        _logger.info("Starting Whisper Wayland service")
        _logger.info("Usage:")
        if self.config:
            _logger.info(f"  - Press and hold {self.config.hotkey} to record audio")
        _logger.info("  - Release to stop recording and transcribe")
        _logger.info("  - Transcribed text will be inserted at cursor position")
        _logger.info("  - Press Ctrl+C to exit")

        # Log available text insertion methods
        if self.component_manager and self.component_manager.text_inserter:
            available_methods = self.component_manager.text_inserter.get_available_methods()
            preferred_method = self.component_manager.text_inserter.get_preferred_method()
            _logger.info(f"  - Text insertion method: {preferred_method}")
            _logger.debug(f"  - Available methods: {available_methods}")

    def cleanup(self) -> None:
        """Clean up application resources."""
        if self.component_manager:
            self.component_manager.cleanup()
