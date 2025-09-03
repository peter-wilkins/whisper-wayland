"""Whisper Wayland - Test Audio Generator

Generates minimal test audio data for connection testing.
"""

import struct


class TestAudioGenerator:
    """Generates test audio data for API testing."""

    def __init__(self) -> None:
        """Initialize test audio generator."""
        pass

    def create_test_audio(self) -> bytes:
        """Create minimal test audio data for connection testing.

        Returns:
            Minimal WAV audio data
        """
        # Create 1 second of silence at 16kHz, 16-bit mono
        sample_rate = 16000
        duration = 1.0
        num_samples = int(sample_rate * duration)

        # WAV header
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            36 + num_samples * 2,  # File size
            b"WAVE",
            b"fmt ",
            16,  # PCM format chunk size
            1,  # PCM format
            1,  # Mono
            sample_rate,  # Sample rate
            sample_rate * 2,  # Byte rate
            2,  # Block align
            16,  # Bits per sample
            b"data",
            num_samples * 2,  # Data size
        )

        # Silent audio data
        audio_data = b"\x00" * (num_samples * 2)

        return header + audio_data

    @staticmethod
    def new() -> "TestAudioGenerator":
        """Create test audio generator instance.

        Returns:
            TestAudioGenerator instance
        """
        return TestAudioGenerator()
