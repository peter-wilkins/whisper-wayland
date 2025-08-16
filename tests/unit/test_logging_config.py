"""Unit tests for logging configuration module."""

import logging
import os
import tempfile
from unittest.mock import Mock, patch

import pytest

from whisper_claude.config import Config
from whisper_claude.logging_config import (
    _configure_third_party_loggers,
    get_logger,
    setup_logging,
)


class TestLoggingConfig:
    """Test cases for logging configuration."""

    @pytest.fixture
    def config(self, mock_api_key):
        """Create test configuration."""
        return Config()

    def test_setup_logging_info_level(self, mock_api_key):
        """Test logging setup with INFO level."""
        # Clear LOG_LEVEL and set to INFO for this test
        with patch.dict(os.environ, {"LOG_LEVEL": "INFO"}, clear=False):
            # Ensure LOG_LEVEL is set to INFO by overriding directly
            os.environ["LOG_LEVEL"] = "INFO"
            test_config = Config()

            with patch("logging.getLogger") as mock_get_logger:
                mock_root_logger = Mock()
                mock_get_logger.return_value = mock_root_logger

                setup_logging(test_config)

                mock_root_logger.setLevel.assert_called_with(logging.INFO)
                assert mock_root_logger.addHandler.call_count >= 1

    def test_setup_logging_debug_level(self, mock_api_key):
        """Test logging setup with DEBUG level."""
        with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}):
            test_config = Config()

            with patch("logging.getLogger") as mock_get_logger:
                mock_root_logger = Mock()
                mock_get_logger.return_value = mock_root_logger

                setup_logging(test_config)

                mock_root_logger.setLevel.assert_called_with(logging.DEBUG)

    def test_setup_logging_with_file(self, config):
        """Test logging setup with file handler."""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            log_file = temp_file.name

        try:
            with patch("logging.getLogger") as mock_get_logger:
                mock_root_logger = Mock()
                mock_get_logger.return_value = mock_root_logger

                setup_logging(config, log_file)

                # Should add both console and file handlers
                assert mock_root_logger.addHandler.call_count == 2

        finally:
            os.unlink(log_file)

    def test_setup_logging_file_error(self, config):
        """Test logging setup with file handler error."""
        invalid_file = "/invalid/path/log.txt"

        with patch("logging.getLogger") as mock_get_logger:
            mock_root_logger = Mock()
            mock_get_logger.return_value = mock_root_logger

            # Should not raise an error, just log it
            setup_logging(config, invalid_file)

            # Should still add console handler
            assert mock_root_logger.addHandler.call_count >= 1

    def test_configure_third_party_loggers(self):
        """Test third-party logger configuration."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            _configure_third_party_loggers()

            # Should be called for each third-party logger
            assert mock_get_logger.call_count >= 3
            assert mock_logger.setLevel.call_count >= 3

    def test_get_logger(self):
        """Test get_logger function."""
        with patch("logging.getLogger") as mock_get_logger:
            mock_logger = Mock()
            mock_get_logger.return_value = mock_logger

            result = get_logger("test.module")

            assert result == mock_logger
            mock_get_logger.assert_called_once_with("test.module")

    def test_logging_levels_mapping(self, config, mock_api_key):
        """Test that string log levels are properly mapped."""
        test_levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }

        for level_str, level_int in test_levels.items():
            with patch.dict(
                os.environ, {"OPENAI_API_KEY": "sk-test123", "LOG_LEVEL": level_str}
            ):
                test_config = Config()

                with patch("logging.getLogger") as mock_get_logger:
                    mock_root_logger = Mock()
                    mock_get_logger.return_value = mock_root_logger

                    setup_logging(test_config)

                    mock_root_logger.setLevel.assert_called_with(level_int)

    def test_logging_formatter_selection(self, config):
        """Test that appropriate formatters are selected."""
        # Test DEBUG level gets detailed formatter
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-test123", "LOG_LEVEL": "DEBUG"}
        ):
            debug_config = Config()

        with patch("logging.getLogger") as mock_get_logger, patch(
            "logging.StreamHandler"
        ) as mock_handler_class:
            mock_root_logger = Mock()
            mock_get_logger.return_value = mock_root_logger
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler

            setup_logging(debug_config)

            # Handler should be configured with formatter
            assert mock_handler.setFormatter.called

        # Test INFO level gets simple formatter
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-test123", "LOG_LEVEL": "INFO"}
        ):
            info_config = Config()

        with patch("logging.getLogger") as mock_get_logger, patch(
            "logging.StreamHandler"
        ) as mock_handler_class:
            mock_root_logger = Mock()
            mock_get_logger.return_value = mock_root_logger
            mock_handler = Mock()
            mock_handler_class.return_value = mock_handler

            setup_logging(info_config)

            # Handler should be configured with formatter
            assert mock_handler.setFormatter.called
