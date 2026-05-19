"""Whisper Wayland - Hotkey Handler Tests."""

import unittest.mock

import whisper_wayland.application as application


class TestHotkeyHandler:
    """Test cases for hotkey handler activation modes."""

    def test_push_to_talk_registers_release_callback(self) -> None:
        """Test push-to-talk mode stops recording on key release."""
        key_monitor = unittest.mock.Mock()
        handler = application.HotkeyHandler(
            unittest.mock.Mock(), unittest.mock.Mock(), mode="push_to_talk"
        )

        handler.setup_callbacks(key_monitor)

        key_monitor.set_callback.assert_called_once()
        key_monitor.set_release_callback.assert_called_once()

    def test_toggle_mode_does_not_register_release_callback(self) -> None:
        """Test toggle mode only reacts to key presses."""
        key_monitor = unittest.mock.Mock()
        handler = application.HotkeyHandler(
            unittest.mock.Mock(), unittest.mock.Mock(), mode="toggle"
        )

        handler.setup_callbacks(key_monitor)

        key_monitor.set_callback.assert_called_once()
        key_monitor.set_release_callback.assert_not_called()

    def test_toggle_mode_starts_and_stops_on_press(self) -> None:
        """Test toggle mode alternates recording state on each key press."""
        audio_recorder = unittest.mock.Mock()
        transcription_processor = unittest.mock.Mock()
        transcription_processor.streaming_enabled = False
        audio_recorder.stop_recording.return_value = b"audio"
        handler = application.HotkeyHandler(
            audio_recorder, transcription_processor, mode="toggle"
        )

        with unittest.mock.patch("whisper_wayland.application.hotkey_handler.threading.Thread"):
            handler._on_hotkey_press()
            assert handler.is_recording_active
            audio_recorder.start_recording.assert_called_once()

            handler._on_hotkey_press()
            assert not handler.is_recording_active
            audio_recorder.stop_recording.assert_called_once()

    def test_streaming_mode_skips_batch_recording(self) -> None:
        """Test streaming mode starts and stops through transcription processor."""
        audio_recorder = unittest.mock.Mock()
        transcription_processor = unittest.mock.Mock()
        transcription_processor.streaming_enabled = True
        transcription_processor.start_streaming.return_value = True
        handler = application.HotkeyHandler(
            audio_recorder, transcription_processor, mode="toggle"
        )

        with unittest.mock.patch("whisper_wayland.application.hotkey_handler.threading.Thread"):
            handler._on_hotkey_press()
            assert handler.is_recording_active
            transcription_processor.start_streaming.assert_called_once()
            audio_recorder.start_recording.assert_not_called()

            handler._on_hotkey_press()
            assert not handler.is_recording_active
            audio_recorder.stop_recording.assert_not_called()

    def test_streaming_start_failure_falls_back_to_batch(self) -> None:
        """Test failed streaming setup falls back to batch recording."""
        audio_recorder = unittest.mock.Mock()
        transcription_processor = unittest.mock.Mock()
        transcription_processor.streaming_enabled = True
        transcription_processor.start_streaming.return_value = False
        handler = application.HotkeyHandler(
            audio_recorder, transcription_processor, mode="toggle"
        )

        handler._on_hotkey_press()

        assert handler.is_recording_active
        transcription_processor.start_streaming.assert_called_once()
        audio_recorder.start_recording.assert_called_once()
