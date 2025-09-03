"""Whisper Wayland - Audio Recorder

Handles audio capture using PyAudio with configurable quality settings
and comprehensive error handling.
"""

import io
import logging
import threading
import time
import typing
import wave

import pyaudio

import whisper_wayland.config as config

_logger = logging.getLogger(__name__)


class AudioRecordingError(Exception):
    """Raised when audio recording operations fail."""

    pass


class AudioRecorder:
    """Audio recorder using PyAudio for cross-platform audio capture.

    Provides push-to-talk functionality with configurable audio quality
    and comprehensive error handling.
    """

    def __init__(self, config: config.Config) -> None:
        """Initialize audio recorder with configuration.

        Args:
            config: Configuration instance

        Raises:
            AudioRecordingError: If PyAudio initialization fails
        """
        self.config = config
        self._audio: typing.Optional[pyaudio.PyAudio] = None
        self._stream: typing.Optional[pyaudio.Stream] = None
        self._recording = False
        self._recording_thread: typing.Optional[threading.Thread] = None
        self._audio_data: typing.Optional[bytes] = None
        self._lock = threading.Lock()

        self._initialize_audio()
        _logger.info("Audio recorder initialized successfully")
        _logger.debug(
            f"Audio config: sample_rate={config.audio_sample_rate}, "
            f"chunk_size={config.audio_chunk_size}, "
            f"max_duration={config.max_recording_duration}s"
        )

    def _initialize_audio(self) -> None:
        """Initialize PyAudio instance with error handling."""
        try:
            self._audio = pyaudio.PyAudio()
            self._validate_audio_system()
            _logger.debug("PyAudio initialized successfully")
        except Exception as e:
            _logger.error(f"Failed to initialize PyAudio: {e}")
            raise AudioRecordingError(f"PyAudio initialization failed: {e}") from e

    def _validate_audio_system(self) -> None:
        """Validate audio system availability and configuration."""
        if not self._audio:
            raise AudioRecordingError("PyAudio not initialized")

        try:
            # Check for available input devices
            device_count = self._audio.get_device_count()
            input_devices = []

            for i in range(device_count):
                device_info = self._audio.get_device_info_by_index(i)
                if device_info["maxInputChannels"] > 0:
                    input_devices.append(device_info)

            if not input_devices:
                raise AudioRecordingError("No audio input devices found")

            _logger.debug(f"Found {len(input_devices)} audio input devices")

            # Test audio format support
            try:
                self._audio.is_format_supported(
                    rate=self.config.audio_sample_rate,
                    input_device=None,
                    input_channels=1,
                    input_format=pyaudio.paInt16,
                )
            except ValueError as e:
                _logger.warning(f"Audio format may not be fully supported: {e}")

        except Exception as e:
            _logger.error(f"Audio system validation failed: {e}")
            raise AudioRecordingError(f"Audio system validation failed: {e}") from e

    def start_recording(self) -> None:
        """Start audio recording in a separate thread.

        Raises:
            AudioRecordingError: If recording cannot be started
        """
        with self._lock:
            if self._recording:
                _logger.warning("Recording already in progress")
                return

            try:
                self._recording = True
                self._audio_data = None
                self._recording_thread = threading.Thread(target=self._record_audio, daemon=True)
                self._recording_thread.start()
                _logger.info("Audio recording started")
            except Exception as e:
                self._recording = False
                _logger.error(f"Failed to start recording: {e}")
                raise AudioRecordingError(f"Failed to start recording: {e}") from e

    def stop_recording(self) -> typing.Optional[bytes]:
        """Stop audio recording and return recorded data.

        Returns:
            Recorded audio data as WAV bytes, or None if no data recorded

        Raises:
            AudioRecordingError: If stopping recording fails
        """
        with self._lock:
            if not self._recording:
                _logger.warning("No recording in progress")
                return None

            try:
                self._recording = False
                _logger.debug("Stopping audio recording...")

                # Wait for recording thread to finish
                if self._recording_thread and self._recording_thread.is_alive():
                    self._recording_thread.join(timeout=5.0)
                    if self._recording_thread.is_alive():
                        _logger.error("Recording thread did not stop within timeout")
                        raise AudioRecordingError("Recording thread timeout")

                self._cleanup_stream()

                audio_data = self._audio_data
                self._audio_data = None
                self._recording_thread = None

                if audio_data:
                    _logger.info(f"Audio recording stopped, captured {len(audio_data)} bytes")
                else:
                    _logger.warning("No audio data captured")

                return audio_data

            except Exception as e:
                _logger.error(f"Failed to stop recording: {e}")
                raise AudioRecordingError(f"Failed to stop recording: {e}") from e

    def _record_audio(self) -> None:
        """Internal method to handle audio recording in separate thread."""
        frames = []
        start_time = time.time()
        max_duration = self.config.max_recording_duration

        try:
            if not self._audio:
                _logger.error("Audio system not initialized")
                return
            self._stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.config.audio_sample_rate,
                input=True,
                frames_per_buffer=self.config.audio_chunk_size,
            )

            _logger.debug(f"Audio stream opened, recording for up to {max_duration}s")

            while self._recording:
                if time.time() - start_time >= max_duration:
                    _logger.info(f"Maximum recording duration ({max_duration}s) reached")
                    break

                try:
                    data = self._stream.read(
                        self.config.audio_chunk_size, exception_on_overflow=False
                    )
                    frames.append(data)
                except Exception as e:
                    _logger.error(f"Error reading audio data: {e}")
                    break

        except Exception as e:
            _logger.error(f"Error setting up audio stream: {e}")
            return

        finally:
            self._cleanup_stream()

        # Convert frames to WAV format
        if frames:
            try:
                self._audio_data = self._frames_to_wav(frames)
                _logger.debug(f"Converted {len(frames)} frames to WAV format")
            except Exception as e:
                _logger.error(f"Failed to convert audio frames to WAV: {e}")

    def _cleanup_stream(self) -> None:
        """Clean up audio stream resources."""
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
                _logger.debug("Audio stream cleaned up")
            except Exception as e:
                _logger.error(f"Error cleaning up audio stream: {e}")
            finally:
                self._stream = None

    def _frames_to_wav(self, frames: list) -> bytes:
        """Convert audio frames to WAV format.

        Args:
            frames: List of audio frame data

        Returns:
            WAV-formatted audio data as bytes
        """
        wav_buffer = io.BytesIO()

        try:
            if not self._audio:
                _logger.error("Audio system not initialized")
                return b""
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(self._audio.get_sample_size(pyaudio.paInt16))
                wav_file.setframerate(self.config.audio_sample_rate)
                wav_file.writeframes(b"".join(frames))

            wav_buffer.seek(0)
            return wav_buffer.read()

        except Exception as e:
            _logger.error(f"Failed to create WAV data: {e}")
            raise AudioRecordingError(f"WAV creation failed: {e}") from e

    def is_recording(self) -> bool:
        """Check if recording is currently in progress.

        Returns:
            True if recording is active, False otherwise
        """
        with self._lock:
            return self._recording

    def get_audio_devices(self) -> list:
        """Get list of available audio input devices.

        Returns:
            List of dictionaries containing device information
        """
        devices: list[dict[str, typing.Any]] = []
        if not self._audio:
            return devices

        try:
            device_count = self._audio.get_device_count()
            for i in range(device_count):
                device_info = self._audio.get_device_info_by_index(i)
                if device_info["maxInputChannels"] > 0:
                    devices.append(
                        {
                            "index": i,
                            "name": device_info["name"],
                            "channels": device_info["maxInputChannels"],
                            "sample_rate": device_info["defaultSampleRate"],
                        }
                    )
            _logger.debug(f"Retrieved {len(devices)} audio input devices")
        except Exception as e:
            _logger.error(f"Failed to get audio devices: {e}")

        return devices

    def __del__(self) -> None:
        """Cleanup resources on object destruction."""
        self.close()

    def close(self) -> None:
        """Clean up audio resources."""
        try:
            if self._recording:
                self.stop_recording()

            self._cleanup_stream()

            if self._audio:
                self._audio.terminate()
                self._audio = None
                _logger.debug("Audio recorder closed successfully")

        except Exception as e:
            _logger.error(f"Error closing audio recorder: {e}")

    @staticmethod
    def new(config: config.Config) -> "AudioRecorder":
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
