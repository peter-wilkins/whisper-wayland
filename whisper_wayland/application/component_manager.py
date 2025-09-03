"""Whisper Wayland - Component Manager

Handles initialization, validation, and cleanup of application components.
"""

import logging
import typing

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class ComponentManager:
    """Manages lifecycle of application components."""

    def __init__(self, config: "ww.Config") -> None:
        """Initialize component manager.
        
        Args:
            config: Configuration instance
        """
        self.config = config
        self.audio_recorder: typing.Optional["ww.AudioRecorder"] = None
        self.transcription_client: typing.Optional["ww.TranscriptionClient"] = None
        self.key_monitor: typing.Optional["ww.KeyMonitor"] = None
        self.text_inserter: typing.Optional["ww.TextInserter"] = None

    def initialize_components(self) -> None:
        """Initialize all application components."""
        _logger.info("Initializing application components...")
        
        # Initialize audio recorder
        self.audio_recorder = ww.AudioRecorder.new(self.config)
        
        # Initialize transcription client
        self.transcription_client = ww.TranscriptionClient.new(self.config)
        
        # Initialize key monitor
        self.key_monitor = ww.KeyMonitor.new(self.config)
        
        # Initialize text inserter
        self.text_inserter = ww.TextInserter.new(self.config)
        
        _logger.info("All components initialized successfully")

    def test_components(self) -> None:
        """Test component connectivity and capabilities."""
        # Test API connection
        _logger.info("Testing OpenAI API connection...")
        if self.transcription_client and not self.transcription_client.test_connection():
            _logger.warning("OpenAI API connection test failed, but continuing...")
        
        # Test text insertion capability
        _logger.info("Testing text insertion capability...")
        if self.text_inserter and not self.text_inserter.test_insertion():
            _logger.warning("Text insertion test failed, but continuing...")

    def validate_components(self) -> bool:
        """Validate that all required components are initialized.
        
        Returns:
            True if all components are valid, False otherwise
        """
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

    def cleanup(self) -> None:
        """Clean up all component resources."""
        _logger.info("Cleaning up application components...")
        
        try:
            if self.key_monitor:
                self.key_monitor.close()

            if self.audio_recorder:
                self.audio_recorder.close()

            if self.transcription_client:
                self.transcription_client.close()

            if self.text_inserter:
                self.text_inserter.close()

            _logger.info("Component cleanup completed")

        except Exception as e:
            _logger.error(f"Error during component cleanup: {e}")

    @staticmethod
    def new(config: "ww.Config") -> "ComponentManager":
        """Create and initialize component manager.
        
        Args:
            config: Configuration instance
            
        Returns:
            ComponentManager instance
        """
        manager = ComponentManager(config)
        manager.initialize_components()
        manager.test_components()
        return manager