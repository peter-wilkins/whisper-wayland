"""Realtime streaming transcription client tests."""

import io
import unittest.mock
import wave

import whisper_wayland as ww
from whisper_wayland.transcription_client.realtime_streaming_client import (
    RealtimeStreamingTranscriptionClient,
)

STREAMING_SAMPLE_RATE = 24000
PCM16_SAMPLE_WIDTH_BYTES = 2


def test_frames_to_wav_uses_streaming_sample_rate() -> None:
    """Test fallback WAV generation uses streaming audio settings."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    audio = unittest.mock.Mock()
    audio.get_sample_size.return_value = PCM16_SAMPLE_WIDTH_BYTES
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._frames = [b"\x00\x00" * 100]

    wav_data = client._frames_to_wav()

    with wave.open(io.BytesIO(wav_data), "rb") as wav_file:
        assert wav_file.getframerate() == STREAMING_SAMPLE_RATE
        assert wav_file.getnchannels() == 1
        assert wav_file.getsampwidth() == PCM16_SAMPLE_WIDTH_BYTES

    audio.get_sample_size.assert_called_once()


def test_stop_returns_fallback_audio_when_no_transcript() -> None:
    """Test streaming stop returns captured audio for batch fallback."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.streaming_completion_timeout_secs = 0.1
    audio = unittest.mock.Mock()
    audio.get_sample_size.return_value = PCM16_SAMPLE_WIDTH_BYTES
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._frames = [b"\x00\x00" * 100]

    result = client.stop()

    assert result.text == ""
    assert result.fallback_audio


def test_start_returns_false_when_audio_capture_fails() -> None:
    """Test streaming does not report started if microphone setup fails."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.audio_chunk_size = 1024
    config.max_recording_duration = 30
    audio = unittest.mock.Mock()
    audio.open.side_effect = OSError("no microphone")
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)

    with unittest.mock.patch.object(client, "_run_websocket_thread"):
        assert not client.start()
