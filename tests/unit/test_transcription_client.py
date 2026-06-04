"""Whisper Wayland - Transcription Client Tests

Unit tests for transcription client module including
OpenAI API integration and error handling."""

import json
import os
import unittest.mock

import openai
import pytest

import whisper_wayland as ww
import whisper_wayland.transcription_client as transcription_client

CAVEMAN_MAX_OUTPUT_TOKENS = 256
LOCAL_API_CUSTOM_TIMEOUT_SECS = 0.75


class TestTranscriptionClient:
    """Test cases for TranscriptionClient class."""

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcription_client_initialization(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription client initialization."""
        mock_client = unittest.mock.Mock()
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)

        assert client.config == test_config
        assert client._client == mock_client
        mock_openai_class.assert_called_once_with(
            api_key=test_config.openai_api_key,
            timeout=test_config.transcription_request_timeout_secs,
            max_retries=0,
        )

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcription_client_initialization_failure(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription client initialization failure."""
        mock_openai_class.side_effect = Exception("OpenAI init failed")

        with pytest.raises(
            transcription_client.TranscriptionError, match="OpenAI client initialization failed"
        ):
            transcription_client.TranscriptionClient(test_config)

    def test_model_name_mapping(self, test_config: "ww.Config") -> None:
        """Test model name mapping to API-compatible names."""
        with unittest.mock.patch(
            "whisper_wayland.transcription_client.client_validator.openai.OpenAI"
        ):
            client = transcription_client.TranscriptionClient(test_config)

            # Test various model mappings
            assert client._map_model_name("tiny") == "whisper-1"
            assert client._map_model_name("base") == "whisper-1"
            assert client._map_model_name("large-v3") == "whisper-1"
            assert client._map_model_name("whisper-1") == "whisper-1"
            assert client._map_model_name("gpt-4o-transcribe") == "gpt-4o-transcribe"
            assert client._map_model_name("gpt-4o-mini-transcribe") == "gpt-4o-mini-transcribe"
            assert client._map_model_name("unknown-future-model") == "unknown-future-model"

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcribe_audio_success(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test successful audio transcription."""
        mock_client = unittest.mock.Mock()
        mock_transcription = unittest.mock.Mock()
        mock_transcription.create.return_value = "This is transcribed text."
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)

        test_audio = b"fake_audio_data"
        result = client.transcribe_audio(test_audio)

        assert result == "This is transcribed text."
        mock_transcription.create.assert_called_once()

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcribe_audio_empty_data(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription with empty audio data."""
        mock_client = unittest.mock.Mock()
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)

        result = client.transcribe_audio(b"")
        assert result is None

        result = client.transcribe_audio(None)  # type: ignore[arg-type]
        assert result is None

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcribe_audio_api_errors(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription with various OpenAI API errors."""
        mock_client = unittest.mock.Mock()
        mock_transcription = unittest.mock.Mock()
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        test_audio = b"fake_audio_data"

        # Test rate limit error
        mock_transcription.create.side_effect = openai.RateLimitError(
            "Rate limit exceeded", response=unittest.mock.Mock(), body=None
        )
        with pytest.raises(
            transcription_client.TranscriptionError, match="API rate limit exceeded"
        ):
            client.transcribe_audio(test_audio)

        # Test authentication error
        mock_transcription.create.side_effect = openai.AuthenticationError(
            "Invalid API key", response=unittest.mock.Mock(), body=None
        )
        with pytest.raises(transcription_client.TranscriptionError, match="API error"):
            client.transcribe_audio(test_audio)

        # Test general API error
        mock_request = unittest.mock.Mock()
        mock_transcription.create.side_effect = openai.APIError(
            "API error", request=mock_request, body=None
        )
        with pytest.raises(transcription_client.TranscriptionError, match="API error"):
            client.transcribe_audio(test_audio)

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcribe_audio_with_retries(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription with retry logic."""
        mock_client = unittest.mock.Mock()
        mock_transcription = unittest.mock.Mock()
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        test_audio = b"fake_audio_data"

        # First call fails, second succeeds
        mock_transcription.create.side_effect = [
            Exception("Temporary error"),
            "Transcription successful",
        ]

        with unittest.mock.patch("time.sleep"):  # Speed up test by mocking sleep
            result = client.transcribe_audio(test_audio, max_retries=2)

        assert result == "Transcription successful"
        assert mock_transcription.create.call_count == ww.Constants.EXPECTED_DEVICE_COUNT

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcribe_audio_uses_configured_retry_count(
        self, mock_openai_class: unittest.mock.MagicMock
    ) -> None:
        """Test default transcription retries come from configuration."""
        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TRANSCRIPTION_MAX_RETRIES": "0",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            mock_client = unittest.mock.Mock()
            mock_transcription = unittest.mock.Mock()
            mock_transcription.create.side_effect = Exception("Persistent error")
            mock_client.audio.transcriptions = mock_transcription
            mock_openai_class.return_value = mock_client

            client = transcription_client.TranscriptionClient(test_config)

            with pytest.raises(transcription_client.TranscriptionError):
                client.transcribe_audio(b"fake_audio_data")

        mock_transcription.create.assert_called_once()

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcribe_audio_max_retries_exceeded(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription when max retries are exceeded."""
        mock_client = unittest.mock.Mock()
        mock_transcription = unittest.mock.Mock()
        mock_transcription.create.side_effect = Exception("Persistent error")
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        test_audio = b"fake_audio_data"

        with unittest.mock.patch("time.sleep"):  # Speed up test
            with pytest.raises(
                transcription_client.TranscriptionError, match="Transcription failed"
            ):
                client.transcribe_audio(test_audio, max_retries=1)

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcribe_audio_empty_result(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription with empty result."""
        mock_client = unittest.mock.Mock()
        mock_transcription = unittest.mock.Mock()
        mock_transcription.create.return_value = ""
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        test_audio = b"fake_audio_data"

        result = client.transcribe_audio(test_audio)
        assert result == ""

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_test_connection_success(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test successful API connection test."""
        mock_client = unittest.mock.Mock()
        mock_transcription = unittest.mock.Mock()
        mock_transcription.create.return_value = "Test successful"
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        result = client.test_connection()

        assert result is True
        mock_transcription.create.assert_called_once()

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_test_connection_failure(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test API connection test failure."""
        mock_client = unittest.mock.Mock()
        mock_transcription = unittest.mock.Mock()
        mock_transcription.create.side_effect = Exception("Connection failed")
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        result = client.test_connection()

        assert result is False

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_create_test_audio(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test creation of test audio data."""
        mock_client = unittest.mock.Mock()
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        test_audio = client._create_test_audio()

        assert isinstance(test_audio, bytes)
        assert len(test_audio) > ww.Constants.WAV_HEADER_SIZE  # Should include WAV header

        # Check WAV header magic
        assert test_audio.startswith(b"RIFF")
        assert b"WAVE" in test_audio[:12]

    def test_get_supported_models(self, test_config: "ww.Config") -> None:
        """Test getting supported models list."""
        with unittest.mock.patch(
            "whisper_wayland.transcription_client.client_validator.openai.OpenAI"
        ):
            client = transcription_client.TranscriptionClient(test_config)
            models = client.get_supported_models()

            assert isinstance(models, list)
            assert "whisper-1" in models
            assert "base" in models
            assert "large-v3" in models

    def test_get_supported_languages(self, test_config: "ww.Config") -> None:
        """Test getting supported languages list."""
        with unittest.mock.patch(
            "whisper_wayland.transcription_client.client_validator.openai.OpenAI"
        ):
            client = transcription_client.TranscriptionClient(test_config)
            languages = client.get_supported_languages()

            assert isinstance(languages, list)
            assert "en" in languages
            assert "es" in languages
            assert "fr" in languages

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_client_close(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription client cleanup."""
        mock_client = unittest.mock.Mock()
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        client.close()

        assert client._client is None

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_transcribe_with_custom_language(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test transcription with custom language parameter."""
        mock_client = unittest.mock.Mock()
        mock_transcription = unittest.mock.Mock()
        mock_transcription.create.return_value = "Texto transcrito"
        mock_client.audio.transcriptions = mock_transcription
        mock_openai_class.return_value = mock_client

        client = transcription_client.TranscriptionClient(test_config)
        test_audio = b"fake_audio_data"

        result = client.transcribe_audio(test_audio, language="es")

        assert result == "Texto transcrito"
        # Verify the correct parameters were passed
        call_args = mock_transcription.create.call_args
        assert call_args.kwargs["language"] == "es"

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_post_process_text_raw_mode(
        self, mock_openai_class: unittest.mock.MagicMock, test_config: "ww.Config"
    ) -> None:
        """Test raw mode returns text without an API call."""
        mock_client = unittest.mock.Mock()
        mock_openai_class.return_value = mock_client
        client = transcription_client.TranscriptionClient(test_config)

        assert client.post_process_text("raw text") == "raw text"
        mock_client.responses.create.assert_not_called()

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_post_process_text_clean_mode(self, mock_openai_class: unittest.mock.MagicMock) -> None:
        """Test clean mode rewrites transcript using responses API."""
        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TEXT_POST_PROCESS_MODE": "clean",
                "TEXT_POST_PROCESS_MODEL": "gpt-test",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            mock_client = unittest.mock.Mock()
            mock_response = unittest.mock.Mock()
            mock_response.output_text = "Clean text."
            mock_client.responses.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            client = transcription_client.TranscriptionClient(test_config)

            assert client.post_process_text("clean text") == "Clean text."
            mock_client.responses.create.assert_called_once()
            call_args = mock_client.responses.create.call_args
            assert call_args.kwargs["model"] == "gpt-test"

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_post_process_text_caveman_mode(
        self, mock_openai_class: unittest.mock.MagicMock
    ) -> None:
        """Test caveman mode rewrites transcript into terse text."""
        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TEXT_POST_PROCESS_MODE": "caveman",
                "TEXT_POST_PROCESS_MODEL": "gpt-test",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            mock_client = unittest.mock.Mock()
            mock_response = unittest.mock.Mock()
            mock_response.output_text = "UX slow. Need one blob paste."
            mock_client.responses.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            client = transcription_client.TranscriptionClient(test_config)

            assert client.post_process_text("the UX is really slow") == (
                "UX slow. Need one blob paste."
            )
            call_args = mock_client.responses.create.call_args
            assert call_args.kwargs["max_output_tokens"] == CAVEMAN_MAX_OUTPUT_TOKENS
            assert "caveman style" in call_args.kwargs["input"][0]["content"]

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_post_process_text_caveman_local_model(
        self, mock_openai_class: unittest.mock.MagicMock
    ) -> None:
        """Test local caveman mode skips API and removes filler."""
        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TEXT_POST_PROCESS_MODE": "caveman",
                "TEXT_POST_PROCESS_MODEL": "local",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            mock_client = unittest.mock.Mock()
            mock_openai_class.return_value = mock_client
            client = transcription_client.TranscriptionClient(test_config)

            assert client.post_process_text(
                "uh well yes yes it is basically working thank you"
            ) == "Yes it is working"
            mock_client.responses.create.assert_not_called()

    @unittest.mock.patch("whisper_wayland.transcription_client.transcription_client.urllib.request.urlopen")
    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_post_process_text_uses_local_api_provider(
        self,
        mock_openai_class: unittest.mock.MagicMock,
        mock_urlopen: unittest.mock.MagicMock,
    ) -> None:
        """Test local personal dictionary API rewrites transcript first."""
        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TEXT_POST_PROCESS_MODE": "clean",
                "TEXT_POST_PROCESS_PROVIDERS": "local-api,openai,local",
                "TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS": "0.75",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            mock_client = unittest.mock.Mock()
            mock_openai_class.return_value = mock_client
            response = unittest.mock.Mock()
            response.status = 200
            response.read.return_value = json.dumps(
                {
                    "insertionText": "Core Product Principle",
                    "backend": "workflow-manager-local-rules",
                    "confidence": 0.94,
                }
            ).encode("utf-8")
            response.__enter__ = unittest.mock.Mock(return_value=response)
            response.__exit__ = unittest.mock.Mock(return_value=None)
            mock_urlopen.return_value = response
            client = transcription_client.TranscriptionClient(test_config)

            assert client.post_process_text("yeah call product principle") == (
                "Core Product Principle"
            )

            mock_client.responses.create.assert_not_called()
            request = mock_urlopen.call_args.args[0]
            payload = json.loads(request.data.decode("utf-8"))
            assert request.full_url == "http://127.0.0.1:8765/v1/transcript/rewrite"
            assert mock_urlopen.call_args.kwargs["timeout"] == LOCAL_API_CUSTOM_TIMEOUT_SECS
            assert payload["rawTranscriptText"] == "yeah call product principle"
            assert payload["principalId"] == "local-user"
            assert payload["target"] == "codex-terminal"

    @unittest.mock.patch("whisper_wayland.transcription_client.transcription_client.urllib.request.urlopen")
    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_post_process_text_local_api_falls_back_to_openai(
        self,
        mock_openai_class: unittest.mock.MagicMock,
        mock_urlopen: unittest.mock.MagicMock,
    ) -> None:
        """Test local API failure falls through to next configured provider."""
        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TEXT_POST_PROCESS_MODE": "clean",
                "TEXT_POST_PROCESS_MODEL": "gpt-test",
                "TEXT_POST_PROCESS_PROVIDERS": "local-api,openai,local",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            mock_urlopen.side_effect = TimeoutError("slow")
            mock_client = unittest.mock.Mock()
            mock_response = unittest.mock.Mock()
            mock_response.output_text = "OpenAI cleaned."
            mock_client.responses.create.return_value = mock_response
            mock_openai_class.return_value = mock_client
            client = transcription_client.TranscriptionClient(test_config)

            assert client.post_process_text("openai clean this") == "OpenAI cleaned."
            mock_client.responses.create.assert_called_once()

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_post_process_text_caveman_falls_back_to_local_on_error(
        self, mock_openai_class: unittest.mock.MagicMock
    ) -> None:
        """Test caveman mode uses local cleanup if model post-processing fails."""
        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TEXT_POST_PROCESS_MODE": "caveman",
                "TEXT_POST_PROCESS_MODEL": "gpt-test",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            mock_client = unittest.mock.Mock()
            mock_client.responses.create.side_effect = Exception("model blocked")
            mock_openai_class.return_value = mock_client
            client = transcription_client.TranscriptionClient(test_config)

            assert client.post_process_text("um this is actually actually fine") == (
                "This is fine"
            )

    @unittest.mock.patch("whisper_wayland.transcription_client.client_validator.openai.OpenAI")
    def test_post_process_text_falls_back_on_error(
        self, mock_openai_class: unittest.mock.MagicMock
    ) -> None:
        """Test post-processing returns raw transcript if API call fails."""
        with unittest.mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test123", "TEXT_POST_PROCESS_MODE": "snappy"},
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            mock_client = unittest.mock.Mock()
            mock_client.responses.create.side_effect = Exception("post-process failed")
            mock_openai_class.return_value = mock_client
            client = transcription_client.TranscriptionClient(test_config)

            assert client.post_process_text("keep this") == "keep this"

    def test_create_transcription_client(self) -> None:
        """Test TranscriptionClient.new static method."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            test_config = ww.Config()

        with unittest.mock.patch(
            "whisper_wayland.transcription_client.TranscriptionClient.__init__", return_value=None
        ):
            result = transcription_client.TranscriptionClient.new(test_config)

            assert isinstance(result, transcription_client.TranscriptionClient)
