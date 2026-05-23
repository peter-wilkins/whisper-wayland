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
        status_indicator = unittest.mock.Mock()
        transcription_processor.streaming_enabled = False
        audio_recorder.stop_recording.return_value = b"audio"
        handler = application.HotkeyHandler(
            audio_recorder,
            transcription_processor,
            mode="toggle",
            status_indicator=status_indicator,
        )

        with unittest.mock.patch(
            "whisper_wayland.application.hotkey_handler.threading.Thread"
        ), unittest.mock.patch(
            "whisper_wayland.application.hotkey_handler.time.monotonic",
            side_effect=[1.0, 2.0],
        ):
            handler._on_hotkey_press()
            assert handler.is_recording_active
            audio_recorder.start_recording.assert_called_once()
            status_indicator.recording.assert_called_once()

            handler._on_hotkey_press()
            assert not handler.is_recording_active
            audio_recorder.stop_recording.assert_called_once()
            status_indicator.transcribing.assert_called_once()

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
        status_indicator = unittest.mock.Mock()
        transcription_processor.streaming_enabled = True
        transcription_processor.start_streaming.return_value = False
        handler = application.HotkeyHandler(
            audio_recorder,
            transcription_processor,
            mode="toggle",
            status_indicator=status_indicator,
        )

        handler._on_hotkey_press()

        assert handler.is_recording_active
        transcription_processor.start_streaming.assert_called_once()
        audio_recorder.start_recording.assert_called_once()
        status_indicator.recording.assert_called_once()

    def test_hotkey_press_ignored_while_transcribing(self) -> None:
        """Test a new recording cannot start while prior transcription is running."""
        audio_recorder = unittest.mock.Mock()
        transcription_processor = unittest.mock.Mock()
        transcription_processor.streaming_enabled = True
        handler = application.HotkeyHandler(
            audio_recorder,
            transcription_processor,
            mode="push_to_talk",
        )
        handler._transcribing_active = True

        handler._on_hotkey_press()

        transcription_processor.start_streaming.assert_not_called()
        audio_recorder.start_recording.assert_not_called()

    def test_short_streaming_tap_is_cancelled(self) -> None:
        """Test jitter taps cancel streaming instead of transcribing."""
        audio_recorder = unittest.mock.Mock()
        transcription_processor = unittest.mock.Mock()
        status_indicator = unittest.mock.Mock()
        transcription_processor.streaming_enabled = True
        transcription_processor.start_streaming.return_value = True
        handler = application.HotkeyHandler(
            audio_recorder,
            transcription_processor,
            mode="push_to_talk",
            status_indicator=status_indicator,
        )

        with unittest.mock.patch(
            "whisper_wayland.application.hotkey_handler.time.monotonic",
            side_effect=[1.0, 1.1],
        ):
            handler._on_hotkey_press()
            handler._on_hotkey_release()

        transcription_processor.cancel_streaming.assert_called_once()
        transcription_processor.stop_streaming.assert_not_called()
        status_indicator.idle.assert_called_once()

    def test_short_batch_tap_is_cancelled(self) -> None:
        """Test jitter taps cancel batch recording instead of transcribing."""
        audio_recorder = unittest.mock.Mock()
        transcription_processor = unittest.mock.Mock()
        status_indicator = unittest.mock.Mock()
        transcription_processor.streaming_enabled = False
        handler = application.HotkeyHandler(
            audio_recorder,
            transcription_processor,
            mode="push_to_talk",
            status_indicator=status_indicator,
        )

        with unittest.mock.patch(
            "whisper_wayland.application.hotkey_handler.time.monotonic",
            side_effect=[1.0, 1.1],
        ):
            handler._on_hotkey_press()
            handler._on_hotkey_release()

        audio_recorder.stop_recording.assert_called_once()
        transcription_processor.process_audio.assert_not_called()
        status_indicator.idle.assert_called_once()

    def test_batch_recording_runs_processor_in_background_thread(self) -> None:
        """Test batch audio is passed to the transcription processor task."""
        audio_recorder = unittest.mock.Mock()
        transcription_processor = unittest.mock.Mock()
        transcription_processor.streaming_enabled = False
        audio_recorder.stop_recording.return_value = b"audio"
        handler = application.HotkeyHandler(
            audio_recorder,
            transcription_processor,
            mode="push_to_talk",
        )

        with unittest.mock.patch(
            "whisper_wayland.application.hotkey_handler.threading.Thread"
        ) as mock_thread, unittest.mock.patch(
            "whisper_wayland.application.hotkey_handler.time.monotonic",
            side_effect=[1.0, 2.0],
        ):
            handler._on_hotkey_press()
            handler._on_hotkey_release()

        mock_thread.assert_called_once_with(
            target=handler._run_transcription_task,
            args=(transcription_processor.process_audio, b"audio"),
            daemon=True,
        )
        mock_thread.return_value.start.assert_called_once()
