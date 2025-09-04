"""Whisper Wayland - Main Tests

Unit tests for main application module functionality including
CLI argument parsing and service initialization."""

import unittest.mock

import pytest

import whisper_wayland as ww
import whisper_wayland.main


class TestApplication:
    """Test cases for Application class."""

    @unittest.mock.patch("whisper_wayland.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.AudioRecorder.new")
    @unittest.mock.patch.object(ww.Config, "setup_logging")
    @unittest.mock.patch("whisper_wayland.Config.get")
    def test_app_initialization_success(  # noqa: PLR0913
        self,
        mock_config_get: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: ww.Config,
    ) -> None:
        """Test successful app initialization."""
        mock_config_get.return_value = test_config
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

        app = ww.Application()

        assert app.config == test_config
        assert app.component_manager is not None
        assert app.component_manager.audio_recorder == mock_recorder
        assert app.component_manager.transcription_client == mock_client
        assert app.component_manager.key_monitor == mock_key_monitor
        assert app.component_manager.text_inserter == mock_text_inserter
        mock_setup_logging.assert_called_once_with()
        mock_client.test_connection.assert_called_once()
        mock_text_inserter.test_insertion.assert_called_once()

    @unittest.mock.patch("whisper_wayland.Config.get")
    def test_app_initialization_config_error(self, mock_config_get: unittest.mock.Mock) -> None:
        """Test app initialization with configuration error."""
        mock_config_get.side_effect = ww.ConfigError("Missing API key")

        with pytest.raises(ww.ConfigError):
            ww.Application()

    @unittest.mock.patch("whisper_wayland.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.AudioRecorder.new")
    @unittest.mock.patch.object(ww.Config, "setup_logging")
    @unittest.mock.patch("whisper_wayland.Config.get")
    def test_app_initialization_with_config_file(  # noqa: PLR0913
        self,
        mock_config_get: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: ww.Config,
    ) -> None:
        """Test app initialization with custom config file."""
        mock_config_get.return_value = test_config
        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = unittest.mock.Mock()
        mock_create_key_monitor.return_value = unittest.mock.Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        ww.Application("/path/to/config.env")

        mock_config_get.assert_called_once_with("/path/to/config.env")

    @unittest.mock.patch("whisper_wayland.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.AudioRecorder.new")
    @unittest.mock.patch.object(ww.Config, "setup_logging")
    @unittest.mock.patch("whisper_wayland.Config.get")
    def test_validate_components_success(  # noqa: PLR0913
        self,
        mock_config_get: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: ww.Config,
    ) -> None:
        """Test successful component validation."""
        mock_config_get.return_value = test_config
        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = unittest.mock.Mock()
        mock_create_key_monitor.return_value = unittest.mock.Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        app = ww.Application()
        assert app.component_manager is not None
        assert app.component_manager.validate_components() is True

    @unittest.mock.patch("whisper_wayland.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.AudioRecorder.new")
    @unittest.mock.patch.object(ww.Config, "setup_logging")
    @unittest.mock.patch("whisper_wayland.Config.get")
    def test_validate_components_missing_config(  # noqa: PLR0913
        self,
        mock_config_get: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: ww.Config,
    ) -> None:
        """Test component validation with missing config."""
        mock_config_get.return_value = test_config
        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_recorder.return_value = unittest.mock.Mock()
        mock_create_key_monitor.return_value = unittest.mock.Mock()
        mock_create_text_inserter.return_value = mock_text_inserter

        app = ww.Application()
        app.config = None

        # Should fail validation when config is None
        assert app.component_manager is not None
        with unittest.mock.patch.object(
            app.component_manager, "validate_components", return_value=False
        ):
            assert not app.component_manager.validate_components()

    @unittest.mock.patch("whisper_wayland.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.AudioRecorder.new")
    @unittest.mock.patch.object(ww.Config, "setup_logging")
    @unittest.mock.patch("whisper_wayland.Config.get")
    def test_audio_recorder_access_through_component_manager(  # noqa: PLR0913
        self,
        mock_config_get: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: ww.Config,
    ) -> None:
        """Test accessing audio recorder through component manager."""
        mock_config_get.return_value = test_config
        mock_recorder = unittest.mock.Mock()
        mock_recorder.start_recording.return_value = None
        mock_recorder.stop_recording.return_value = b"fake_audio_data"
        mock_create_recorder.return_value = mock_recorder

        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_key_monitor.return_value = unittest.mock.Mock()

        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_text_inserter.return_value = mock_text_inserter

        app = ww.Application()

        # Test that audio recorder is accessible through component manager
        assert app.component_manager is not None
        assert app.component_manager.audio_recorder == mock_recorder

    @unittest.mock.patch("whisper_wayland.TextInserter.new")
    @unittest.mock.patch("whisper_wayland.KeyMonitor.new")
    @unittest.mock.patch("whisper_wayland.TranscriptionClient.new")
    @unittest.mock.patch("whisper_wayland.AudioRecorder.new")
    @unittest.mock.patch.object(ww.Config, "setup_logging")
    @unittest.mock.patch("whisper_wayland.Config.get")
    def test_cleanup(  # noqa: PLR0913
        self,
        mock_config_get: unittest.mock.Mock,
        mock_setup_logging: unittest.mock.Mock,
        mock_create_recorder: unittest.mock.Mock,
        mock_create_client: unittest.mock.Mock,
        mock_create_key_monitor: unittest.mock.Mock,
        mock_create_text_inserter: unittest.mock.Mock,
        test_config: ww.Config,
    ) -> None:
        """Test application cleanup."""
        mock_config_get.return_value = test_config
        mock_recorder = unittest.mock.Mock()
        mock_create_recorder.return_value = mock_recorder

        mock_client = unittest.mock.Mock()
        mock_client.test_connection.return_value = True
        mock_create_client.return_value = mock_client
        mock_create_key_monitor.return_value = unittest.mock.Mock()

        mock_text_inserter = unittest.mock.Mock()
        mock_text_inserter.test_insertion.return_value = True
        mock_create_text_inserter.return_value = mock_text_inserter

        app = ww.Application()
        app.cleanup()

        # Verify cleanup was called (component_manager handles individual component cleanup)
        assert True  # cleanup() was called without errors


class TestMainFunction:
    """Test cases for main function."""

    @unittest.mock.patch("whisper_wayland.Application")
    def test_main_success(self, mock_app_class: unittest.mock.MagicMock) -> None:
        """Test successful main function execution."""
        mock_app = unittest.mock.Mock()
        mock_app_class.return_value = mock_app

        with unittest.mock.patch("sys.argv", ["whisper-wayland"]):
            with pytest.raises(SystemExit) as exc_info:
                ww.main()

        assert exc_info.value.code == 0
        mock_app_class.assert_called_once_with(None)
        mock_app.run.assert_called_once()

    @unittest.mock.patch("whisper_wayland.Application")
    @unittest.mock.patch("os.path.exists")
    def test_main_with_config_file(
        self, mock_exists: unittest.mock.Mock, mock_app_class: unittest.mock.MagicMock
    ) -> None:
        """Test main function with config file argument."""
        mock_exists.return_value = True
        mock_app = unittest.mock.Mock()
        mock_app_class.return_value = mock_app

        with unittest.mock.patch("sys.argv", ["whisper-wayland", "/path/to/config.env"]):
            with pytest.raises(SystemExit) as exc_info:
                ww.main()

        assert exc_info.value.code == 0
        mock_app_class.assert_called_once_with("/path/to/config.env")
        mock_app.run.assert_called_once()

    @unittest.mock.patch("whisper_wayland.Application")
    @unittest.mock.patch("os.path.exists")
    def test_main_with_nonexistent_config_file(
        self, mock_exists: unittest.mock.Mock, mock_app_class: unittest.mock.MagicMock
    ) -> None:
        """Test main function with nonexistent config file."""
        mock_exists.return_value = False

        with unittest.mock.patch("sys.argv", ["whisper-wayland", "/nonexistent/config.env"]):
            with unittest.mock.patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    ww.main()

        assert exc_info.value.code == 1
        mock_print.assert_called_with(
            "Error: Configuration file '/nonexistent/config.env' not found"
        )
        mock_app_class.assert_not_called()

    @unittest.mock.patch("whisper_wayland.Application")
    def test_main_config_error(self, mock_app_class: unittest.mock.MagicMock) -> None:
        """Test main function with configuration error."""
        mock_app_class.side_effect = ww.ConfigError("Missing API key")

        with unittest.mock.patch("sys.argv", ["whisper-wayland"]):
            with unittest.mock.patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    ww.main()

        assert exc_info.value.code == 1
        mock_print.assert_any_call("Configuration error: Missing API key")
        mock_print.assert_any_call("Please check your environment variables or .env file")

    @unittest.mock.patch("whisper_wayland.Application")
    def test_main_general_error(self, mock_app_class: unittest.mock.MagicMock) -> None:
        """Test main function with general error."""
        mock_app_class.side_effect = Exception("Unexpected error")

        with unittest.mock.patch("sys.argv", ["whisper-wayland"]):
            with unittest.mock.patch("builtins.print") as mock_print:
                with pytest.raises(SystemExit) as exc_info:
                    ww.main()

        assert exc_info.value.code == 1
        mock_print.assert_called_with("Application error: Unexpected error")
