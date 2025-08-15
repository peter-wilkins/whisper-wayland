"""Integration tests using real OpenAI API.

These tests require a valid OPENAI_API_KEY environment variable
and will make actual API calls to OpenAI.
"""

import os
from unittest.mock import patch
import pytest

from whisper_claude.config import Config, ConfigError
from whisper_claude.transcription_client import TranscriptionClient, create_transcription_client


class TestRealAPIIntegration:
    """Integration tests with real OpenAI API."""

    @pytest.fixture
    def config(self):
        """Create configuration for real API testing."""
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set, skipping real API tests")
        
        return Config()

    def test_real_api_connection(self, config):
        """Test connection to real OpenAI API."""
        client = create_transcription_client(config)
        
        # Test connection
        result = client.test_connection()
        
        assert result is True
        client.close()

    def test_real_api_transcription_with_test_audio(self, config):
        """Test transcription with minimal test audio."""
        client = create_transcription_client(config)
        
        try:
            # Use the client's test audio (minimal silence)
            test_audio = client._create_test_audio()
            
            # Transcribe the test audio
            result = client.transcribe_audio(test_audio, max_retries=1)
            
            # Result should be a string (may be empty for silence)
            assert isinstance(result, str)
            
        finally:
            client.close()

    def test_real_api_with_various_models(self, config):
        """Test transcription with different model configurations."""
        models_to_test = ["base", "tiny", "whisper-1"]
        
        for model in models_to_test:
            # Update config for this model
            with patch.dict(os.environ, {"WHISPER_MODEL": model}):
                test_config = Config()
                
                client = create_transcription_client(test_config)
                
                try:
                    # Test connection with this model
                    result = client.test_connection()
                    assert result is True
                    
                finally:
                    client.close()

    def test_real_api_error_handling(self, config):
        """Test error handling with real API."""
        # Create client with invalid model to test validation
        client = create_transcription_client(config)
        
        try:
            # Test with empty audio (should handle gracefully)
            result = client.transcribe_audio(b"", max_retries=1)
            assert result is None
            
            # Test with very small invalid audio data
            result = client.transcribe_audio(b"invalid", max_retries=1)
            # Should either return None or raise TranscriptionError
            assert result is None or isinstance(result, str)
            
        finally:
            client.close()

    def test_real_api_language_parameter(self, config):
        """Test transcription with language parameter."""
        client = create_transcription_client(config)
        
        try:
            test_audio = client._create_test_audio()
            
            # Test with English
            result_en = client.transcribe_audio(test_audio, language="en", max_retries=1)
            assert isinstance(result_en, str)
            
            # Test with Spanish (should still work with silence)
            result_es = client.transcribe_audio(test_audio, language="es", max_retries=1)
            assert isinstance(result_es, str)
            
        finally:
            client.close()

    def test_real_api_supported_features(self, config):
        """Test supported models and languages."""
        client = create_transcription_client(config)
        
        try:
            # Test supported models list
            models = client.get_supported_models()
            assert isinstance(models, list)
            assert len(models) > 0
            assert "whisper-1" in models
            
            # Test supported languages list
            languages = client.get_supported_languages()
            assert isinstance(languages, list)
            assert len(languages) > 0
            assert "en" in languages
            
        finally:
            client.close()


class TestConfigurationIntegration:
    """Integration tests for configuration loading."""

    def test_config_with_real_env_file(self):
        """Test configuration loading from real .env file."""
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set, skipping env file test")
        
        import tempfile
        
        # Create temporary .env file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.env', delete=False) as f:
            f.write(f"OPENAI_API_KEY={api_key}\n")
            f.write("WHISPER_MODEL=large\n")
            f.write("AUDIO_SAMPLE_RATE=44100\n")
            f.write("LOG_LEVEL=DEBUG\n")
            env_file_path = f.name

        try:
            # Load config from env file
            config = Config(env_file_path)
            
            assert config.openai_api_key == api_key
            assert config.whisper_model == "large"
            assert config.audio_sample_rate == 44100
            assert config.log_level == "DEBUG"
            
        finally:
            os.unlink(env_file_path)

    def test_config_validation_with_invalid_api_key(self):
        """Test configuration validation with invalid API key format."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "invalid-key-format"}):
            # Should still create config (validation happens at API level)
            config = Config()
            assert config.openai_api_key == "invalid-key-format"
            
            # But transcription client should fail on API calls
            client = create_transcription_client(config)
            
            try:
                # Connection test should fail
                result = client.test_connection()
                assert result is False
                
            finally:
                client.close()


@pytest.mark.slow
class TestEndToEndIntegration:
    """End-to-end integration tests (marked as slow)."""

    def test_full_audio_workflow_simulation(self):
        """Test full workflow simulation without actual audio recording."""
        api_key = os.environ.get('OPENAI_API_KEY')
        if not api_key:
            pytest.skip("OPENAI_API_KEY not set, skipping E2E test")
        
        # Create config
        config = Config()
        
        # Create transcription client
        transcription_client = create_transcription_client(config)
        
        try:
            # Test connection
            assert transcription_client.test_connection() is True
            
            # Simulate audio data (use test audio)
            audio_data = transcription_client._create_test_audio()
            assert audio_data is not None
            assert len(audio_data) > 0
            
            # Transcribe audio
            transcription = transcription_client.transcribe_audio(audio_data)
            assert isinstance(transcription, str)
            
            # Simulate saving to file
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
                f.write(f"Test transcription: {transcription}\n")
                temp_file = f.name
            
            try:
                # Verify file was created and has content
                with open(temp_file, 'r') as f:
                    content = f.read()
                    assert "Test transcription:" in content
                    
            finally:
                os.unlink(temp_file)
                
        finally:
            transcription_client.close()