"""Whisper Wayland - Component Manager

Handles initialization, validation, and cleanup of application components.
"""

import whisper_wayland as ww


class ComponentManager:
    """Manages lifecycle of application components."""

    def __init__(self, config: "ww.Config") -> None:
        """Initialize component manager.

        Args:
            config: Configuration instance
        """
        self.config = config
        self.audio_recorder = ww.AudioRecorder.new(config)
        self.transcription_client = ww.TranscriptionClient.new(config)
        self.key_monitor = ww.KeyMonitor.new(config)
        self.text_inserter = ww.TextInserter.new(config)

    @staticmethod
    def new(config: "ww.Config") -> "ComponentManager":
        """Create and initialize component manager.

        Args:
            config: Configuration instance

        Returns:
            ComponentManager instance
        """
        manager = ComponentManager(config)
        return manager
