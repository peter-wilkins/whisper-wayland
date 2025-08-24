"""Unit tests for main application module."""

from unittest.mock import Mock, patch

import pytest

from whisper_wayland.config import Config, ConfigError
from whisper_wayland.main import WhisperClaudeApp, main


class TestWhisperClaudeApp:
    """Test cases for WhisperClaudeApp class."""

    @pytest.fixture
    def config(self, mock_api_key):
        """Create test configuration."""
        return Config()

    @patch("whisper_wayland.main.create_text_inserter")
    @patch("whisper_wayland.main.create_key_monitor")
    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_app_initialization_success(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        mock_create_key_monitor,
        mock_create_text_inserter,
        config,
    ):
        """Test successful app initialization."""
        mock_get_config.return_value = config
        mock_recorder = Mock()
        mock_client = Mock()
        mock_key_monitor = Mock()
        mock_text_inserter = Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter.test_insertion.return_value = True
        mock_create_recorder.return_value = mock_recorder
        mock_create_client.return_value = mock_client
        mock_create_key_monitor.return_value = mock_key_monitor
        mock_create_text_inserter.return_value = mock_text_inserter

        app = WhisperClaudeApp()

        assert app.config == config
        assert app.audio_recorder == mock_recorder
        assert app.transcription_client == mock_client
        assert app.key_monitor == mock_key_monitor
        assert app.text_inserter == mock_text_inserter
        mock_setup_logging.assert_called_once_with(config)
        mock_client.test_connection.assert_called_once()
        mock_text_inserter.test_insertion.assert_called_once()

    @patch("whisper_wayland.main.get_config")
    def test_app_initialization_config_error(self, mock_get_config):
        """Test app initialization with configuration error."""
        mock_get_config.side_effect = ConfigError("Missing API key")

        with pytest.raises(ConfigError):
            WhisperClaudeApp()

    @patch("whisper_wayland.main.create_text_inserter")
    @patch("whisper_wayland.main.create_key_monitor")
    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_app_initialization_with_config_file(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        mock_create_key_monitor,
        mock_create_text_inserter,
        config,
    ):
        """Test app initialization with custom config file."""
        mock_get_config.return_value = config
        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = Mock()
        mock_create_key_monitor.return_value = Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        WhisperClaudeApp("/path/to/config.env")

        mock_get_config.assert_called_once_with("/path/to/config.env")

    @patch("whisper_wayland.main.create_text_inserter")
    @patch("whisper_wayland.main.create_key_monitor")
    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_validate_components_success(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        mock_create_key_monitor,
        mock_create_text_inserter,
        config,
    ):
        """Test successful component validation."""
        mock_get_config.return_value = config
        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = Mock()
        mock_create_key_monitor.return_value = Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        app = WhisperClaudeApp()
        assert app._validate_components() is True

    @patch("whisper_wayland.main.create_text_inserter")
    @patch("whisper_wayland.main.create_key_monitor")
    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_validate_components_missing_config(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        mock_create_key_monitor,
        mock_create_text_inserter,
        config,
    ):
        """Test component validation with missing config."""
        mock_get_config.return_value = config
        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = Mock()
        mock_create_key_monitor.return_value = Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        app = WhisperClaudeApp()
        app.config = None

        assert app._validate_components() is False

    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_record_audio_session(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        config,
    ):
        """Test audio recording session."""
        mock_get_config.return_value = config
        mock_recorder = Mock()
        mock_recorder.start_recording.return_value = None
        mock_recorder.stop_recording.return_value = b"fake_audio_data"
        mock_create_recorder.return_value = mock_recorder

        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client

        app = WhisperClaudeApp()

        with patch("builtins.input", return_value=""):
            audio_data = app._record_audio_session()

        assert audio_data == b"fake_audio_data"
        mock_recorder.start_recording.assert_called_once()
        mock_recorder.stop_recording.assert_called_once()

    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_record_audio_session_no_recorder(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        config,
    ):
        """Test audio recording session without recorder."""
        mock_get_config.return_value = config
        mock_create_recorder.return_value = Mock()

        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client

        app = WhisperClaudeApp()
        app.audio_recorder = None

        audio_data = app._record_audio_session()
        assert audio_data is None

    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_transcribe_audio(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        config,
    ):
        """Test audio transcription."""
        mock_get_config.return_value = config
        mock_create_recorder.return_value = Mock()

        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_client.transcribe_audio.return_value = "Transcribed text"
        mock_create_client.return_value = mock_client

        app = WhisperClaudeApp()

        result = app._transcribe_audio(b"fake_audio_data")

        assert result == "Transcribed text"
        mock_client.transcribe_audio.assert_called_once_with(b"fake_audio_data")

    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_transcribe_audio_no_client(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        config,
    ):
        """Test audio transcription without client."""
        mock_get_config.return_value = config
        mock_create_recorder.return_value = Mock()
        mock_create_client.return_value = Mock()

        app = WhisperClaudeApp()
        app.transcription_client = None

        result = app._transcribe_audio(b"fake_audio_data")
        assert result is None

    @patch("whisper_wayland.main.create_text_inserter")
    @patch("whisper_wayland.main.create_key_monitor")
    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_insert_text(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        mock_create_key_monitor,
        mock_create_text_inserter,
        config,
    ):
        """Test text insertion functionality."""
        mock_get_config.return_value = config
        mock_create_recorder.return_value = Mock()

        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_key_monitor.return_value = Mock()

        mock_text_inserter = Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_text_inserter.insert_text.return_value = True
        mock_create_text_inserter.return_value = mock_text_inserter

        app = WhisperClaudeApp()

        with patch("builtins.print"):
            app._insert_text("Test transcription")

        mock_text_inserter.insert_text.assert_called_once_with("Test transcription")

    @patch("whisper_wayland.main.create_text_inserter")
    @patch("whisper_wayland.main.create_key_monitor")
    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_cleanup(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        mock_create_key_monitor,
        mock_create_text_inserter,
        config,
    ):
        """Test application cleanup."""
        mock_get_config.return_value = config
        mock_recorder = Mock()
        mock_create_recorder.return_value = mock_recorder

        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_key_monitor.return_value = Mock()

        mock_text_inserter = Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_text_inserter.return_value = mock_text_inserter

        app = WhisperClaudeApp()
        app.cleanup()

        mock_recorder.close.assert_called_once()
        mock_client.close.assert_called_once()
        mock_text_inserter.close.assert_called_once()

    @patch("whisper_wayland.main.create_transcription_client")
    @patch("whisper_wayland.main.create_audio_recorder")
    @patch("whisper_wayland.main.setup_logging")
    @patch("whisper_wayland.main.get_config")
    def test_wait_for_recording_trigger_keyboard_interrupt(
        self,
        mock_get_config,
        mock_setup_logging,
        mock_create_recorder,
        mock_create_client,
        config,
    ):
        """Test recording trigger with keyboard interrupt."""
        mock_get_config.return_value = config
        mock_create_recorder.return_value = Mock()

        mock_client = Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client

        app = WhisperClaudeApp()

        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            with patch("builtins.print"):
                app._wait_for_recording_trigger()

        assert not app._running


class TestMainFunction:
    """Test cases for main function."""

    @patch("whisper_wayland.main.WhisperClaudeApp")
    def test_main_success(self, mock_app_class):
        """Test successful main function execution."""
        mock_app = Mock()
        mock_app_class.return_value = mock_app

        with patch("sys.argv", ["whisper-wayland"]):
            main()

        mock_app_class.assert_called_once_with(None)
        mock_app.run.assert_called_once()

    @patch("whisper_wayland.main.WhisperClaudeApp")
    @patch("os.path.exists")
    def test_main_with_config_file(self, mock_exists, mock_app_class):
        """Test main function with config file argument."""
        mock_exists.return_value = True
        mock_app = Mock()
        mock_app_class.return_value = mock_app

        with patch("sys.argv", ["whisper-wayland", "/path/to/config.env"]):
            main()

        mock_app_class.assert_called_once_with("/path/to/config.env")
        mock_app.run.assert_called_once()

    @patch("whisper_wayland.main.WhisperClaudeApp")
    @patch("os.path.exists")
    def test_main_with_nonexistent_config_file(self, mock_exists, mock_app_class):
        """Test main function with nonexistent config file."""
        mock_exists.return_value = False

        with patch("sys.argv", ["whisper-wayland", "/nonexistent/config.env"]):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1
        mock_print.assert_called_with(
            "Error: Configuration file '/nonexistent/config.env' not found"
        )
        mock_app_class.assert_not_called()

    @patch("whisper_wayland.main.WhisperClaudeApp")
    def test_main_config_error(self, mock_app_class):
        """Test main function with configuration error."""
        mock_app_class.side_effect = ConfigError("Missing API key")

        with patch("sys.argv", ["whisper-wayland"]):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1
        mock_print.assert_any_call("Configuration error: Missing API key")
        mock_print.assert_any_call(
            "Please check your environment variables or .env file"
        )

    @patch("whisper_wayland.main.WhisperClaudeApp")
    def test_main_general_error(self, mock_app_class):
        """Test main function with general error."""
        mock_app_class.side_effect = Exception("Unexpected error")

        with patch("sys.argv", ["whisper-wayland"]):
            with patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    main()

        assert exc_info.value.code == 1
        mock_print.assert_called_with("Application error: Unexpected error")
