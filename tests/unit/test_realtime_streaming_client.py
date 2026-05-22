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
CONFIGURED_INPUT_DEVICE_INDEX = 2


def test_frames_to_wav_uses_streaming_sample_rate() -> None:
    """Test fallback WAV generation uses streaming audio settings."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    audio.get_sample_size.return_value = PCM16_SAMPLE_WIDTH_BYTES
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._frames = [b"\x00\x00" * 2400]

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
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    audio.get_sample_size.return_value = PCM16_SAMPLE_WIDTH_BYTES
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._frames = [b"\x00\x00" * 2400]

    result = client.stop()

    assert result.text == ""
    assert result.fallback_audio


def test_stop_skips_fallback_for_too_short_audio() -> None:
    """Test streaming stop does not retry too-short audio through batch transcription."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.streaming_completion_timeout_secs = 0.1
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    audio.get_sample_size.return_value = PCM16_SAMPLE_WIDTH_BYTES
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._frames = [b"\x00\x00" * 100]

    result = client.stop()

    assert result.text == ""
    assert result.fallback_audio is None


def test_cancel_stops_streaming_without_fallback() -> None:
    """Test cancellation shuts down realtime streaming without producing fallback audio."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.streaming_completion_timeout_secs = 0.1
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._streaming = True
    client._frames = [b"\x00\x00" * 2400]

    client.cancel()

    assert not client._streaming
    assert client._cancel_requested


def test_start_returns_false_when_audio_capture_fails() -> None:
    """Test streaming does not report started if microphone setup fails."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.audio_chunk_size = 1024
    config.max_recording_duration = 30
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    audio.open.side_effect = OSError("no microphone")
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)

    with unittest.mock.patch.object(client, "_run_websocket_thread"):
        assert not client.start()


def test_record_audio_loop_uses_configured_input_device() -> None:
    """Test realtime capture uses the configured microphone device."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.audio_chunk_size = 1024
    config.max_recording_duration = 30
    config.audio_input_device_index = CONFIGURED_INPUT_DEVICE_INDEX
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    audio.get_device_info_by_index.return_value = {
        "name": "External USB Microphone",
        "maxInputChannels": 1,
    }
    stream = unittest.mock.Mock()
    audio.open.return_value = stream
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._stop_event.set()

    client._record_audio_loop()

    assert audio.open.call_args.kwargs["input_device_index"] == CONFIGURED_INPUT_DEVICE_INDEX
    stream.stop_stream.assert_called_once()
    stream.close.assert_called_once()


def test_session_update_uses_current_realtime_shape() -> None:
    """Test websocket session update uses the current Realtime API shape."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.streaming_transcription_model = "gpt-4o-transcribe"
    config.streaming_turn_detection_enabled = False
    config.streaming_vad_silence_duration_ms = 700
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)

    event = client._session_update_event()

    assert event == {
        "type": "session.update",
        "session": {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": STREAMING_SAMPLE_RATE,
                    },
                    "transcription": {
                        "model": "gpt-4o-transcribe",
                        "language": "en",
                    },
                    "turn_detection": None,
                },
            },
        },
    }


def test_session_update_can_enable_server_vad() -> None:
    """Test websocket session update can commit completed chunks on pauses."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.streaming_transcription_model = "gpt-4o-transcribe"
    config.streaming_turn_detection_enabled = True
    config.streaming_vad_silence_duration_ms = 900
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)

    event = client._session_update_event()

    assert event["session"]["audio"]["input"]["turn_detection"] == {
        "type": "server_vad",
        "threshold": 0.5,
        "prefix_padding_ms": 300,
        "silence_duration_ms": 900,
    }


def test_completed_vad_chunk_is_delivered_to_callback() -> None:
    """Test completed VAD chunks are delivered without waiting for final release."""
    callback = unittest.mock.Mock()
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.streaming_turn_detection_enabled = True
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    client = RealtimeStreamingTranscriptionClient(
        config,
        audio=audio,
        transcript_callback=callback,
    )

    client._deliver_transcript_chunk("Hello there.")

    callback.assert_called_once_with("Hello there.")
    assert client._chunks_delivered


def test_stop_reports_delivered_chunks_without_fallback() -> None:
    """Test stop does not duplicate text after chunks were already inserted."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_sample_rate = STREAMING_SAMPLE_RATE
    config.streaming_completion_timeout_secs = 0.1
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._chunks_delivered = True
    client._frames = [b"\x00\x00" * 2400]

    result = client.stop()

    assert result.chunks_delivered
    assert result.fallback_audio is None


def test_stop_uses_short_timeout_after_delivered_vad_chunks() -> None:
    """Test stop does not wait full completion timeout once chunks were inserted."""
    config = unittest.mock.Mock(spec=ww.Config)
    config.streaming_completion_timeout_secs = 4
    config.streaming_turn_detection_enabled = True
    config.audio_input_device_index = None
    config.audio_input_device_name = ""
    audio = unittest.mock.Mock()
    client = RealtimeStreamingTranscriptionClient(config, audio=audio)
    client._chunks_delivered = True

    assert client._stop_join_timeout_secs() == client.WEBSOCKET_SHUTDOWN_GRACE_SECS
