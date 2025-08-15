"""Pytest configuration and fixtures."""

import os
from unittest.mock import patch

import pytest


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


@pytest.fixture(autouse=True)
def clean_environment():
    """Clean environment for each test."""
    # Store original environment
    original_env = dict(os.environ)

    # Ensure clean test environment
    test_env_vars = [
        "OPENAI_API_KEY",
        "WHISPER_MODEL",
        "AUDIO_SAMPLE_RATE",
        "AUDIO_CHUNK_SIZE",
        "MAX_RECORDING_DURATION",
        "LOG_LEVEL",
        "HOTKEY",
        "SERVICE_NAME",
        "SERVICE_DESCRIPTION",
        "DOCKER_AUDIO_DEVICE",
        "DOCKER_DISPLAY_VAR",
        "TEXT_INSERTION_DELAY",
        "TEXT_INSERTION_METHOD",
    ]

    yield

    # Restore original environment
    for key in test_env_vars:
        if key in os.environ:
            if key in original_env:
                os.environ[key] = original_env[key]
            else:
                del os.environ[key]
        elif key in original_env:
            os.environ[key] = original_env[key]


@pytest.fixture
def mock_api_key():
    """Provide mock API key for tests."""
    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
        yield "sk-test123"


@pytest.fixture
def temp_transcription_file():
    """Create temporary transcription file for tests."""
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        temp_file = f.name

    yield temp_file

    # Cleanup
    try:
        os.unlink(temp_file)
    except OSError:
        pass  # File may have been deleted by test
