"""Whisper Wayland - Main Tests

Unit tests for main application module functionality including
CLI argument parsing and service initialization."""

import unittest.mock

import pytest

import whisper_wayland.config as config
import whisper_wayland.main as main


class TestWhisperClaudeApp:
    """Test cases for WhisperClaudeApp class."""

    @unittest.mock.patch("whisper_wayland.main.text_inserter.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.main.key_monitor.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_app_initialization_success(  # noqa: PLR0913
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test successful app initialization."""
        mock_get_config.return_value = test_config
        mock_recorder = unittest.mock.Mock()
        mock_client = unittest.mock.Mock()
        mock_key_monitor = unittest.mock.Mock()
        mock_text_inserter = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter.test_insertion.return_value = True
        mock_create_recorder.return_value = mock_recorder
        mock_create_client.return_value = mock_client
        mock_create_key_monitor.return_value = mock_key_monitor
        mock_create_text_inserter.return_value = mock_text_inserter

        app = main.WhisperClaudeApp()

        assert app.config == test_config
        assert app.audio_recorder == mock_recorder
        assert app.transcription_client == mock_client
        assert app.key_monitor == mock_key_monitor
        assert app.text_inserter == mock_text_inserter
        mock_setup_logging.assert_called_once_with(test_config)
        mock_client.test_connection.assert_called_once()
        mock_text_inserter.test_insertion.assert_called_once()

    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_app_initialization_config_error(self, mock_get_config: unittest.mock.Mock) -> None:
        """Test app initialization with configuration error."""
        mock_get_config.side_effect = config.ConfigError("Missing API key")

        with pytest.raises(config.ConfigError):
            main.WhisperClaudeApp()

    @unittest.mock.patch("whisper_wayland.main.text_inserter.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.main.key_monitor.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_app_initialization_with_config_file(  # noqa: PLR0913
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test app initialization with custom config file."""
        mock_get_config.return_value = test_config
        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = unittest.mock.Mock()
        mock_create_key_monitor.return_value = unittest.mock.Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        main.WhisperClaudeApp("/path/to/config.env")

        mock_get_config.assert_called_once_with("/path/to/config.env")

    @unittest.mock.patch("whisper_wayland.main.text_inserter.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.main.key_monitor.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_validate_components_success(  # noqa: PLR0913
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test successful component validation."""
        mock_get_config.return_value = test_config
        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = unittest.mock.Mock()
        mock_create_key_monitor.return_value = unittest.mock.Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        app = main.WhisperClaudeApp()
        assert app._validate_components() is True

    @unittest.mock.patch("whisper_wayland.main.text_inserter.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.main.key_monitor.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_validate_components_missing_config(  # noqa: PLR0913
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test component validation with missing config."""
        mock_get_config.return_value = test_config
        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = unittest.mock.Mock()
        mock_create_key_monitor.return_value = unittest.mock.Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        app = main.WhisperClaudeApp()
        app.config = None

        assert app._validate_components() is False

    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_record_audio_session(
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test audio recording session."""
        mock_get_config.return_value = test_config
        mock_recorder = unittest.mock.Mock()
        mock_recorder.start_recording.return_value = None
        mock_recorder.stop_recording.return_value = b"fake_audio_data"
        mock_create_recorder.return_value = mock_recorder

        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client

        app = main.WhisperClaudeApp()

        with unittest.mock.patch("builtins.input", return_value=""):
            audio_data = app._record_audio_session()

        assert audio_data == b"fake_audio_data"
        mock_recorder.start_recording.assert_called_once()
        mock_recorder.stop_recording.assert_called_once()

    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_record_audio_session_no_recorder(
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test audio recording session without recorder."""
        mock_get_config.return_value = test_config
        mock_create_recorder.return_value = unittest.mock.Mock()

        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client

        app = main.WhisperClaudeApp()
        app.audio_recorder = None

        audio_data = app._record_audio_session()
        assert audio_data is None

    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_transcribe_audio(
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test audio transcription."""
        mock_get_config.return_value = test_config
        mock_create_recorder.return_value = unittest.mock.Mock()

        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_client.transcribe_audio.return_value = "Transcribed text"
        mock_create_client.return_value = mock_client

        app = main.WhisperClaudeApp()

        result = app._transcribe_audio(b"fake_audio_data")

        assert result == "Transcribed text"
        mock_client.transcribe_audio.assert_called_once_with(b"fake_audio_data")

    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_transcribe_audio_no_client(
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test audio transcription without client."""
        mock_get_config.return_value = test_config
        mock_create_recorder.return_value = unittest.mock.Mock()
        mock_create_client.return_value = unittest.mock.Mock()

        app = main.WhisperClaudeApp()
        app.transcription_client = None

        result = app._transcribe_audio(b"fake_audio_data")
        assert result is None

    @unittest.mock.patch("whisper_wayland.main.text_inserter.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.main.key_monitor.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_insert_text(  # noqa: PLR0913
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test text insertion functionality."""
        mock_get_config.return_value = test_config
        mock_create_recorder.return_value = unittest.mock.Mock()

        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_key_monitor.return_value = unittest.mock.Mock()

        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_text_inserter.insert_text.return_value = True
        mock_create_text_inserter.return_value = mock_text_inserter

        app = main.WhisperClaudeApp()

        with unittest.mock.patch("builtins.print"):
            app._insert_text("Test transcription")

        mock_text_inserter.insert_text.assert_called_once_with("Test transcription")

    @unittest.mock.patch("whisper_wayland.main.text_inserter.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.main.key_monitor.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_cleanup(  # noqa: PLR0913
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test application cleanup."""
        mock_get_config.return_value = test_config
        mock_recorder = unittest.mock.Mock()
        mock_create_recorder.return_value = mock_recorder

        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_key_monitor.return_value = unittest.mock.Mock()

        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_text_inserter.return_value = mock_text_inserter

        app = main.WhisperClaudeApp()
        app.cleanup()

        mock_recorder.close.assert_called_once()
        mock_client.close.assert_called_once()
        mock_text_inserter.close.assert_called_once()

    @unittest.mock.patch("whisper_wayland.main.transcription_client.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.main.audio_recorder.AudioRecorder.new")
    @unittest.mock.patch("whisper_wayland.main.logging_config.setup_logging")
    @unittest.mock.patch("whisper_wayland.main.config.get_config")
    def test_wait_for_recording_trigger_keyboard_interrupt(
        self,
        mock_get_config: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        test_config: config.Config,
    ) -> None:
        """Test recording trigger with keyboard interrupt."""
        mock_get_config.return_value = test_config
        mock_create_recorder.return_value = unittest.mock.Mock()

        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client

        app = main.WhisperClaudeApp()

        with unittest.mock.patch("builtins.input", side_effect=KeyboardInterrupt()):
            with unittest.mock.patch("builtins.print"):
                app._wait_for_recording_trigger()

        assert not app._running


class TestMainFunction:
    """Test cases for main function."""

    @unittest.mock.patch("whisper_wayland.main.WhisperClaudeApp")
    def test_main_success(self, mock_app_class: unittest.mock.MagicMock) -> None:
        """Test successful main function execution."""
        mock_app = unittest.mock.Mock()
        mock_app_class.return_value = mock_app

        with unittest.mock.patch("sys.argv", ["whisper-wayland"]):
            main.main()

        mock_app_class.assert_called_once_with(None)
        mock_app.run.assert_called_once()

    @unittest.mock.patch("whisper_wayland.main.WhisperClaudeApp")
    @unittest.mock.patch("os.path.exists")
    def test_main_with_config_file(
        self, mock_exists: unittest.mock.Mock, mock_app_class: unittest.mock.MagicMock
    ) -> None:
        """Test main function with config file argument."""
        mock_exists.return_value = True
        mock_app = unittest.mock.Mock()
        mock_app_class.return_value = mock_app

        with unittest.mock.patch("sys.argv", ["whisper-wayland", "/path/to/config.env"]):
            main.main()

        mock_app_class.assert_called_once_with("/path/to/config.env")
        mock_app.run.assert_called_once()

    @unittest.mock.patch("whisper_wayland.main.WhisperClaudeApp")
    @unittest.mock.patch("os.path.exists")
    def test_main_with_nonexistent_config_file(
        self, mock_exists: unittest.mock.Mock, mock_app_class: unittest.mock.MagicMock
    ) -> None:
        """Test main function with nonexistent config file."""
        mock_exists.return_value = False

        with unittest.mock.patch("sys.argv", ["whisper-wayland", "/nonexistent/config.env"]):
            with unittest.mock.patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main.main()

        assert exc_info.value.code == 1
        mock_print.assert_called_with(
            "Error: Configuration file '/nonexistent/config.env' not found"
        )
        mock_app_class.assert_not_called()

    @unittest.mock.patch("whisper_wayland.main.WhisperClaudeApp")
    def test_main_config_error(self, mock_app_class: unittest.mock.MagicMock) -> None:
        """Test main function with configuration error."""
        mock_app_class.side_effect = config.ConfigError("Missing API key")

        with unittest.mock.patch("sys.argv", ["whisper-wayland"]):
            with unittest.mock.patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main.main()

        assert exc_info.value.code == 1
        mock_print.assert_any_call("Configuration error: Missing API key")
        mock_print.assert_any_call("Please check your environment variables or .env file")

    @unittest.mock.patch("whisper_wayland.main.WhisperClaudeApp")
    def test_main_general_error(self, mock_app_class: unittest.mock.MagicMock) -> None:
        """Test main function with general error."""
        mock_app_class.side_effect = Exception("Unexpected error")

        with unittest.mock.patch("sys.argv", ["whisper-wayland"]):
            with unittest.mock.patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main.main()

        assert exc_info.value.code == 1
        mock_print.assert_called_with("Application error: Unexpected error")
