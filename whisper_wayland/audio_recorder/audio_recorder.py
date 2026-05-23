"""Whisper Wayland - Audio Recorder

Main audio recorder orchestrator that coordinates all audio recording components.
"""

import logging
import typing

import whisper_wayland as ww
from whisper_wayland.audio_recorder.audio_system_validator import (
    AudioSystemValidationError,
    AudioSystemValidator,
)
from whisper_wayland.audio_recorder.recording_engine import RecordingEngine, RecordingEngineError

_logger = logging.getLogger(__name__)


class AudioRecordingError(Exception):
    """Raised when audio recording operations fail."""

    pass


class AudioRecorder:
    """Audio recorder using PyAudio for cross-platform audio capture.

    Provides push-to-talk functionality with configurable audio quality
    and comprehensive error handling.
    """

    def __init__(self, config: "ww.Config") -> None:
        """Initialize audio recorder with configuration.

        Args:
            config: Configuration instance

        Raises:
            AudioRecordingError: If PyAudio initialization fails
        """
        self.config = config

        try:
            self._audio_validator = AudioSystemValidator.new()
            self._audio = None
            self._recording_engine = None
            self._input_device_name = ""
            self._initialize_recording_engine()

            _logger.info("Audio recorder initialized successfully")
            _logger.info(
                "Recording input device: %s (index %s)",
                self._input_device_name,
                self._recording_engine.input_device_index,
            )
            _logger.debug(
                f"Audio config: sample_rate={config.audio_sample_rate}, "
                f"chunk_size={config.audio_chunk_size}, "
                f"max_duration={config.max_recording_duration}s, "
                f"input_device_index={self._recording_engine.input_device_index}"
            )
        except AudioSystemValidationError as e:
            raise AudioRecordingError(str(e)) from e
        except Exception as e:
            _logger.error(f"Failed to initialize audio recorder: {e}")
            raise AudioRecordingError(f"Audio recorder initialization failed: {e}") from e

    def start_recording(self) -> None:
        """Start audio recording in a separate thread.

        Raises:
            AudioRecordingError: If recording cannot be started
        """
        try:
            self._recording_engine.start_recording()
        except RecordingEngineError as e:
            raise AudioRecordingError(str(e)) from e

    def refresh_input_device(self) -> None:
        """Re-check preferred input device and reopen the warmed stream if it changed."""
        if self.is_recording():
            return

        try:
            input_device_index = self._audio_validator.find_preferred_input_device(
                self._audio,
                self.config,
            )
            input_device_name = self._audio_validator.get_input_device_name(
                self._audio,
                input_device_index,
            )

            if (
                self._recording_engine.input_device_index == input_device_index
                and self._input_device_name == input_device_name
            ):
                return

            _logger.info(
                "Audio input device changed: %s (index %s) -> %s (index %s)",
                self._input_device_name,
                self._recording_engine.input_device_index,
                input_device_name,
                input_device_index,
            )
            self._replace_recording_engine(self._audio, input_device_index, input_device_name)
        except Exception as e:
            _logger.warning("Could not refresh audio input device; keeping current stream: %s", e)

    def stop_recording(self) -> typing.Optional[bytes]:
        """Stop audio recording and return recorded data.

        Returns:
            Recorded audio data as WAV bytes, or None if no data recorded

        Raises:
            AudioRecordingError: If stopping recording fails
        """
        try:
            return self._recording_engine.stop_recording()
        except RecordingEngineError as e:
            raise AudioRecordingError(str(e)) from e

    def is_recording(self) -> bool:
        """Check if recording is currently in progress.

        Returns:
            True if recording is active, False otherwise
        """
        return self._recording_engine.is_recording()

    def get_audio_devices(self) -> list[dict[str, typing.Any]]:
        """Get list of available audio input devices.

        Returns:
            List of dictionaries containing device information
        """
        return self._audio_validator.get_audio_devices(self._audio)

    def close(self) -> None:
        """Clean up audio resources."""
        try:
            recording_engine = getattr(self, "_recording_engine", None)
            if recording_engine:
                if recording_engine.is_recording():
                    recording_engine.stop_recording()
                recording_engine.close()

            audio = getattr(self, "_audio", None)
            if audio:
                audio.terminate()
                self._audio = None
                _logger.debug("Audio recorder closed successfully")

        except Exception as e:
            _logger.error(f"Error closing audio recorder: {e}")

    def _initialize_recording_engine(self) -> None:
        """Initialize PyAudio and warm the current preferred input stream."""
        audio = self._audio_validator.initialize_audio()
        self._audio_validator.validate_audio_system(audio, self.config)
        input_device_index = self._audio_validator.find_preferred_input_device(
            audio,
            self.config,
        )
        input_device_name = self._audio_validator.get_input_device_name(
            audio,
            input_device_index,
        )
        self._replace_recording_engine(audio, input_device_index, input_device_name)

    def _replace_recording_engine(
        self,
        audio: typing.Any,
        input_device_index: typing.Optional[int],
        input_device_name: str,
    ) -> None:
        """Swap to a new warmed recording engine."""
        old_engine = self._recording_engine
        old_audio = self._audio

        recording_engine = RecordingEngine.new(audio, self.config, input_device_index)
        recording_engine.prepare_stream()

        self._recording_engine = recording_engine
        self._audio = audio
        self._input_device_name = input_device_name

        if old_engine:
            old_engine.close()
        if old_audio and old_audio is not audio:
            old_audio.terminate()

    def __del__(self) -> None:
        """Cleanup resources on object destruction."""
        self.close()

    @staticmethod
    def new(config: "ww.Config") -> "AudioRecorder":
        """Create and initialize audio recorder instance.

        Args:
            config: Configuration instance

        Returns:
            AudioRecorder instance

        Raises:
            AudioRecordingError: If recorder creation fails
        """
        try:
            return AudioRecorder(config)
        except Exception as e:
            _logger.error(f"Failed to create audio recorder: {e}")
            raise
