"""Whisper Wayland - WAV Converter

Converts audio frames to WAV format for transcription.
"""

import io
import logging
import typing
import wave

import pyaudio

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class WavConverterError(Exception):
    """Raised when WAV conversion operations fail."""

    pass


class WavConverter:
    """Converts audio frames to WAV format."""

    def __init__(self, audio: pyaudio.PyAudio, config: "ww.Config") -> None:
        """Initialize WAV converter.

        Args:
            audio: PyAudio instance
            config: Configuration instance
        """
        self._audio = audio
        self._config = config

    def frames_to_wav(self, frames: list[bytes], sample_rate: typing.Optional[int] = None) -> bytes:
        """Convert audio frames to WAV format.

        Args:
            frames: List of audio frame data
            sample_rate: Sample rate to encode in WAV header, defaults to config value

        Returns:
            WAV-formatted audio data as bytes

        Raises:
            WavConverterError: If WAV conversion fails
        """
        effective_rate = sample_rate if sample_rate is not None else self._config.audio_sample_rate
        wav_buffer = io.BytesIO()

        try:
            with wave.open(wav_buffer, "wb") as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(self._audio.get_sample_size(pyaudio.paInt16))
                wav_file.setframerate(effective_rate)
                wav_file.writeframes(b"".join(frames))

            wav_buffer.seek(0)
            return wav_buffer.read()

        except Exception as e:
            _logger.error(f"Failed to create WAV data: {e}")
            raise WavConverterError(f"WAV creation failed: {e}") from e

    @staticmethod
    def new(audio: pyaudio.PyAudio, config: "ww.Config") -> "WavConverter":
        """Create WAV converter instance.

        Args:
            audio: PyAudio instance
            config: Configuration instance

        Returns:
            WavConverter instance
        """
        return WavConverter(audio, config)
