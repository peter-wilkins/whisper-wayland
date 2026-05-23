"""Whisper Wayland - Audio Recorder

Main audio recorder orchestrator that coordinates all audio recording components.
"""

import logging
import subprocess
import typing

import whisper_wayland as ww
from whisper_wayland.audio_recorder.audio_system_validator import (
    AudioSystemValidationError,
    AudioSystemValidator,
)
from whisper_wayland.audio_recorder.recording_engine import RecordingEngine, RecordingEngineError

_logger = logging.getLogger(__name__)

PACTL_SOURCE_NAME_FIELD_COUNT = 2


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
            if self._should_reinitialize_audio():
                _logger.info("Refreshing PyAudio device list before selecting input")
                self._reinitialize_recording_engine()

            input_device_index = self._audio_validator.find_preferred_input_device(
                self._audio,
                self.config,
                warn_on_missing_explicit=False,
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

    def get_active_input_source(self) -> str:
        """Get the active input device/source name used for recordings."""
        return self._input_device_name

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

    def _reinitialize_recording_engine(self) -> None:
        """Recreate PyAudio so hotplugged devices are visible."""
        old_engine = self._recording_engine
        old_audio = self._audio
        self._recording_engine = None
        self._audio = None

        try:
            self._initialize_recording_engine()
        finally:
            if old_engine:
                old_engine.close()
            if old_audio:
                old_audio.terminate()

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

    def _should_reinitialize_audio(self) -> bool:
        """Return true when PipeWire source state says PyAudio may be stale."""
        available_sources = self._available_pipewire_sources()
        if available_sources is None:
            return False

        active_source = self._input_device_name.strip()
        configured_source = self.config.audio_input_device_name.strip()

        if self._is_concrete_source(active_source) and active_source not in available_sources:
            _logger.info("Active audio source disappeared: %s", active_source)
            return True

        if (
            configured_source
            and active_source.lower() != configured_source.lower()
            and any(configured_source in source.lower() for source in available_sources)
        ):
            _logger.info("Configured audio source appeared: %s", configured_source)
            return True

        return False

    @staticmethod
    def _available_pipewire_sources() -> set[str] | None:
        """Return current pactl source names, or None if pactl is unavailable."""
        result = subprocess.run(
            ["pactl", "list", "short", "sources"],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return None

        sources = set()
        for line in result.stdout.splitlines():
            fields = line.split()
            if len(fields) >= PACTL_SOURCE_NAME_FIELD_COUNT:
                sources.add(fields[1])
        return sources

    @staticmethod
    def _is_concrete_source(source: str) -> bool:
        """Return whether a PyAudio device name is a concrete PipeWire source name."""
        normalized = source.lower()
        return normalized.startswith(("alsa_input.", "bluez_input."))

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
