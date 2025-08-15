"""Unit tests for transcription client module."""

import os
from unittest.mock import Mock, patch

import openai
import pytest

from whisper_claude.config import Config
from whisper_claude.transcription_client import (
    TranscriptionClient,
    TranscriptionError,
    create_transcription_client,
)


class TestTranscriptionClient:
    """Test cases for TranscriptionClient class."""

    @pytest.fixture
    def config(self, mock_api_key):
        """Create test configuration."""
        return Config()

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcription_client_initialization(self, mock_openai_class, config):
        """Test transcription client initialization."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)

        assert client.config == config
        assert client._client == mock_client
        mock_openai_class.assert_called_once_with(api_key="sk-test123")

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcription_client_initialization_failure(
        self, mock_openai_class, config
    ):
        """Test transcription client initialization failure."""
        mock_openai_class.side_effect = Exception("OpenAI init failed")

        with pytest.raises(
            TranscriptionError, match="OpenAI client initialization failed"
        ):
            TranscriptionClient(config)

    def test_model_name_mapping(self, config):
        """Test model name mapping to API-compatible names."""
        with patch("whisper_claude.transcription_client.OpenAI"):
            client = TranscriptionClient(config)

            # Test various model mappings
            assert client._map_model_name("tiny") == "whisper-1"
            assert client._map_model_name("base") == "whisper-1"
            assert client._map_model_name("large-v3") == "whisper-1"
            assert client._map_model_name("whisper-1") == "whisper-1"
            assert client._map_model_name("unknown") == "whisper-1"

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcribe_audio_success(self, mock_openai_class, config):
        """Test successful audio transcription."""
        mock_client = Mock()
        mock_transcription = Mock()
        mock_transcription.create.return_value = "This is transcribed text."
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)

        test_audio = b"fake_audio_data"
        result = client.transcribe_audio(test_audio)

        assert result == "This is transcribed text."
        mock_transcription.create.assert_called_once()

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcribe_audio_empty_data(self, mock_openai_class, config):
        """Test transcription with empty audio data."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)

        result = client.transcribe_audio(b"")
        assert result is None

        result = client.transcribe_audio(None)
        assert result is None

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcribe_audio_api_errors(self, mock_openai_class, config):
        """Test transcription with various OpenAI API errors."""
        mock_client = Mock()
        mock_transcription = Mock()
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        test_audio = b"fake_audio_data"

        # Test rate limit error
        mock_transcription.create.side_effect = openai.RateLimitError(
            "Rate limit exceeded", response=Mock(), body=None
        )
        with pytest.raises(TranscriptionError, match="API rate limit exceeded"):
            client.transcribe_audio(test_audio)

        # Test authentication error
        mock_transcription.create.side_effect = openai.AuthenticationError(
            "Invalid API key", response=Mock(), body=None
        )
        with pytest.raises(TranscriptionError, match="API error"):
            client.transcribe_audio(test_audio)

        # Test general API error
        mock_request = Mock()
        mock_transcription.create.side_effect = openai.APIError(
            "API error", request=mock_request, body=None
        )
        with pytest.raises(TranscriptionError, match="API error"):
            client.transcribe_audio(test_audio)

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcribe_audio_with_retries(self, mock_openai_class, config):
        """Test transcription with retry logic."""
        mock_client = Mock()
        mock_transcription = Mock()
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        test_audio = b"fake_audio_data"

        # First call fails, second succeeds
        mock_transcription.create.side_effect = [
            Exception("Temporary error"),
            "Transcription successful",
        ]

        with patch("time.sleep"):  # Speed up test by mocking sleep
            result = client.transcribe_audio(test_audio, max_retries=2)

        assert result == "Transcription successful"
        assert mock_transcription.create.call_count == 2

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcribe_audio_max_retries_exceeded(self, mock_openai_class, config):
        """Test transcription when max retries are exceeded."""
        mock_client = Mock()
        mock_transcription = Mock()
        mock_transcription.create.side_effect = Exception("Persistent error")
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        test_audio = b"fake_audio_data"

        with patch("time.sleep"):  # Speed up test
            with pytest.raises(TranscriptionError, match="Transcription failed"):
                client.transcribe_audio(test_audio, max_retries=1)

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcribe_audio_empty_result(self, mock_openai_class, config):
        """Test transcription with empty result."""
        mock_client = Mock()
        mock_transcription = Mock()
        mock_transcription.create.return_value = ""
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        test_audio = b"fake_audio_data"

        result = client.transcribe_audio(test_audio)
        assert result == ""

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_test_connection_success(self, mock_openai_class, config):
        """Test successful API connection test."""
        mock_client = Mock()
        mock_transcription = Mock()
        mock_transcription.create.return_value = "Test successful"
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        result = client.test_connection()

        assert result is True
        mock_transcription.create.assert_called_once()

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_test_connection_failure(self, mock_openai_class, config):
        """Test API connection test failure."""
        mock_client = Mock()
        mock_transcription = Mock()
        mock_transcription.create.side_effect = Exception("Connection failed")
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        result = client.test_connection()

        assert result is False

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_create_test_audio(self, mock_openai_class, config):
        """Test creation of test audio data."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        test_audio = client._create_test_audio()

        assert isinstance(test_audio, bytes)
        assert len(test_audio) > 44  # Should include WAV header

        # Check WAV header magic
        assert test_audio.startswith(b"RIFF")
        assert b"WAVE" in test_audio[:12]

    def test_get_supported_models(self, config):
        """Test getting supported models list."""
        with patch("whisper_claude.transcription_client.OpenAI"):
            client = TranscriptionClient(config)
            models = client.get_supported_models()

            assert isinstance(models, list)
            assert "whisper-1" in models
            assert "base" in models
            assert "large-v3" in models

    def test_get_supported_languages(self, config):
        """Test getting supported languages list."""
        with patch("whisper_claude.transcription_client.OpenAI"):
            client = TranscriptionClient(config)
            languages = client.get_supported_languages()

            assert isinstance(languages, list)
            assert "en" in languages
            assert "es" in languages
            assert "fr" in languages

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_client_close(self, mock_openai_class, config):
        """Test transcription client cleanup."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        client.close()

        assert client._client is None

    @patch("whisper_claude.transcription_client.OpenAI")
    def test_transcribe_with_custom_language(self, mock_openai_class, config):
        """Test transcription with custom language parameter."""
        mock_client = Mock()
        mock_transcription = Mock()
        mock_transcription.create.return_value = "Texto transcrito"
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = TranscriptionClient(config)
        test_audio = b"fake_audio_data"

        result = client.transcribe_audio(test_audio, language="es")

        assert result == "Texto transcrito"
        # Verify the correct parameters were passed
        call_args = mock_transcription.create.call_args
        assert call_args.kwargs["language"] == "es"

    def test_create_transcription_client(self):
        """Test create_transcription_client factory function."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            config = Config()

        with patch(
            "whisper_claude.transcription_client.TranscriptionClient"
        ) as mock_client:
            mock_instance = Mock()
            mock_client.return_value = mock_instance

            result = create_transcription_client(config)

            assert result == mock_instance
            mock_client.assert_called_once_with(config)
