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
        self.config = ww.Config.get(config_file)
        self.config.setup_logging()

        self.component_manager = ComponentManager.new(self.config)
        self.transcription_processor = TranscriptionProcessor.new(
            self.component_manager.transcription_client,
            self.component_manager.text_inserter,
        )
        self.hotkey_handler = HotkeyHandler.new(
            self.component_manager.audio_recorder,
            self.transcription_processor,
        )
        self.runtime_manager = RuntimeManager(self)

        self.runtime_manager.setup_signal_handlers()
        self.runtime_manager.setup_hotkey_monitoring()
        self._running = True

    def run(self) -> None:
        """Run the main application loop."""
        try:
            self.runtime_manager.run_main_loop()
        except KeyboardInterrupt:
            _logger.info("Received interrupt signal, shutting down ...")
        except Exception as e:
            _logger.error(f"Application error: {e}")
