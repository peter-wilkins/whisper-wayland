"""Unit tests for configuration module."""

import os
import tempfile
from unittest.mock import patch

import pytest

from whisper_claude.config import Config, ConfigError, get_config


class TestConfig:
    """Test cases for Config class."""

    def test_config_initialization_with_defaults(self):
        """Test config initialization with default values."""
        # Temporarily remove LOG_LEVEL to test default
        old_log_level = os.environ.pop("LOG_LEVEL", None)
        try:
            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
                config = Config()

                assert config.openai_api_key == "sk-test123"
                assert config.whisper_model == "base"
                assert config.audio_sample_rate == 16000
                assert config.audio_chunk_size == 1024
                assert config.max_recording_duration == 30
                assert config.log_level == "INFO"
                assert config.hotkey == "compose"
        finally:
            # Restore LOG_LEVEL if it existed
            if old_log_level:
                os.environ["LOG_LEVEL"] = old_log_level

    def test_config_missing_required_api_key(self):
        """Test config fails when required API key is missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
                Config()

    def test_config_empty_api_key(self):
        """Test config fails when API key is empty."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with pytest.raises(ConfigError, match="OPENAI_API_KEY"):
                Config()

    def test_config_custom_values(self):
        """Test config with custom environment values."""
        env_vars = {
            "OPENAI_API_KEY": "sk-custom123",
            "WHISPER_MODEL": "large",
            "AUDIO_SAMPLE_RATE": "44100",
            "AUDIO_CHUNK_SIZE": "2048",
            "MAX_RECORDING_DURATION": "60",
            "LOG_LEVEL": "DEBUG",
            "HOTKEY": "alt+space",
        }

        with patch.dict(os.environ, env_vars):
            config = Config()

            assert config.openai_api_key == "sk-custom123"
            assert config.whisper_model == "large"
            assert config.audio_sample_rate == 44100
            assert config.audio_chunk_size == 2048
            assert config.max_recording_duration == 60
            assert config.log_level == "DEBUG"
            assert config.hotkey == "alt+space"

    def test_config_invalid_numeric_values(self):
        """Test config validation of numeric values."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            # Invalid sample rate
            with patch.dict(os.environ, {"AUDIO_SAMPLE_RATE": "invalid"}):
                with pytest.raises(ConfigError, match="AUDIO_SAMPLE_RATE"):
                    Config()

            # Negative sample rate
            with patch.dict(os.environ, {"AUDIO_SAMPLE_RATE": "-1000"}):
                with pytest.raises(ConfigError, match="AUDIO_SAMPLE_RATE"):
                    Config()

            # Invalid chunk size
            with patch.dict(os.environ, {"AUDIO_CHUNK_SIZE": "not_a_number"}):
                with pytest.raises(ConfigError, match="AUDIO_CHUNK_SIZE"):
                    Config()

            # Invalid recording duration
            with patch.dict(os.environ, {"MAX_RECORDING_DURATION": "zero"}):
                with pytest.raises(ConfigError, match="MAX_RECORDING_DURATION"):
                    Config()

    def test_config_invalid_log_level(self):
        """Test config handles invalid log levels gracefully."""
        with patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-test123", "LOG_LEVEL": "INVALID_LEVEL"}
        ):
            config = Config()
            assert config.log_level == "INFO"  # Should fallback to default

    def test_config_text_insertion_delay(self):
        """Test text insertion delay configuration."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            # Default value
            config = Config()
            assert config.text_insertion_delay == 0.1

            # Custom value
            with patch.dict(os.environ, {"TEXT_INSERTION_DELAY": "0.5"}):
                config = Config()
                assert config.text_insertion_delay == 0.5

            # Invalid value
            with patch.dict(os.environ, {"TEXT_INSERTION_DELAY": "invalid"}):
                with pytest.raises(ConfigError, match="TEXT_INSERTION_DELAY"):
                    Config()

            # Negative value
            with patch.dict(os.environ, {"TEXT_INSERTION_DELAY": "-1.0"}):
                with pytest.raises(ConfigError, match="TEXT_INSERTION_DELAY"):
                    Config()

    def test_config_text_insertion_method(self):
        """Test text insertion method configuration."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            # Default value
            config = Config()
            assert config.text_insertion_method == "wtype"

            # Valid custom value
            with patch.dict(os.environ, {"TEXT_INSERTION_METHOD": "xdotool"}):
                config = Config()
                assert config.text_insertion_method == "xdotool"

            # Invalid value (should fallback to default)
            with patch.dict(os.environ, {"TEXT_INSERTION_METHOD": "invalid_method"}):
                config = Config()
                assert config.text_insertion_method == "wtype"

    def test_config_service_properties(self):
        """Test service-related configuration properties."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "SERVICE_NAME": "test-service",
                "SERVICE_DESCRIPTION": "Test service description",
                "DOCKER_AUDIO_DEVICE": "/dev/audio",
                "DOCKER_DISPLAY_VAR": "WAYLAND_DISPLAY",
            },
        ):
            config = Config()

            assert config.service_name == "test-service"
            assert config.service_description == "Test service description"
            assert config.docker_audio_device == "/dev/audio"
            assert config.docker_display_var == "WAYLAND_DISPLAY"

    def test_config_load_env_file(self):
        """Test loading configuration from .env file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("OPENAI_API_KEY=sk-envfile123\n")
            f.write("WHISPER_MODEL=small\n")
            f.write("LOG_LEVEL=DEBUG\n")
            env_file_path = f.name

        try:
            config = Config(env_file_path)
            assert config.openai_api_key == "sk-envfile123"
            assert config.whisper_model == "small"
            assert config.log_level == "DEBUG"
        finally:
            os.unlink(env_file_path)

    def test_config_load_nonexistent_env_file(self):
        """Test handling of nonexistent .env file."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            # Should not raise an error, just log a warning
            config = Config("/nonexistent/file.env")
            assert config.openai_api_key == "sk-test123"

    def test_config_safe_summary(self):
        """Test safe configuration summary masks sensitive data."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-sensitive123"}):
            config = Config()
            summary = config._get_safe_config_summary()

            assert summary["openai_api_key"] == "***"
            assert summary["whisper_model"] == "base"
            assert "sk-sensitive123" not in str(summary)

    def test_get_config_function(self):
        """Test get_config helper function."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            config = get_config()
            assert isinstance(config, Config)
            assert config.openai_api_key == "sk-test123"

    def test_get_config_with_file(self):
        """Test get_config with environment file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("OPENAI_API_KEY=sk-filetest123\n")
            env_file_path = f.name

        try:
            config = get_config(env_file_path)
            assert config.openai_api_key == "sk-filetest123"
        finally:
            os.unlink(env_file_path)
