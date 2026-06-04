"""Whisper Wayland - Pytest Configuration

Pytest configuration and fixtures for testing the
Whisper Wayland voice transcription service."""

import os
import tempfile
import typing

import dotenv
import pytest

import whisper_wayland as ww

dotenv.load_dotenv()


def pytest_configure(config: pytest.Config) -> None:
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )


@pytest.fixture(autouse=True)
def clean_environment() -> typing.Generator[None, None, None]:
    """Clean environment for each test."""
    # Store original environment
    original_env = dict(os.environ)

    # Ensure clean test environment
    test_env_vars = [
        "OPENAI_API_KEY",
        "WHISPER_MODEL",
        "TRANSCRIPTION_REQUEST_TIMEOUT_SECS",
        "TRANSCRIPTION_MAX_RETRIES",
        "AUDIO_SAMPLE_RATE",
        "AUDIO_CHUNK_SIZE",
        "AUDIO_PREROLL_SECONDS",
        "AUDIO_LEVEL_MONITOR_ENABLED",
        "AUDIO_LEVEL_AUTO_ADJUST_ENABLED",
        "AUDIO_LEVEL_MANAGE_MICS_ENABLED",
        "AUDIO_LEVEL_CHECK_INTERVAL_SECS",
        "AUDIO_LEVEL_SOURCE",
        "AUDIO_TRANSCRIPTION_NORMALIZATION_ENABLED",
        "AUDIO_TRANSCRIPTION_NORMALIZATION_TARGET_RMS_DBFS",
        "AUDIO_TRANSCRIPTION_NORMALIZATION_MAX_PEAK_AMPLITUDE",
        "AUDIO_TRANSCRIPTION_NORMALIZATION_MAX_GAIN",
        "MAX_RECORDING_DURATION",
        "LOG_LEVEL",
        "HOTKEY",
        "HOTKEY_MODE",
        "TEXT_INSERTION_DELAY",
        "TEXT_INSERTION_METHOD",
        "TEXT_TMUX_TARGET_PANE",
        "TEXT_PASTE_HOTKEY",
        "TEXT_POST_PROCESS_MODE",
        "TEXT_POST_PROCESS_MODEL",
        "TEXT_POST_PROCESS_PROVIDERS",
        "CONTINUUM_CAPTURE_INLET_DIR",
        "STREAMING_TRANSCRIPTION_ENABLED",
        "STREAMING_TRANSCRIPTION_MODEL",
        "STREAMING_SAMPLE_RATE",
        "STREAMING_COMPLETION_TIMEOUT_SECS",
        "STREAMING_DELTA_IDLE_TIMEOUT_SECS",
        "STREAMING_TURN_DETECTION_ENABLED",
        "STREAMING_VAD_SILENCE_DURATION_MS",
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
def test_config() -> typing.Generator[ww.Config, None, None]:
    """Provide test configuration loaded from .env file."""
    # Ensure .env file is loaded and API key is available
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip(
            "OPENAI_API_KEY not found in environment. Ensure .env file is properly configured."
        )

    yield ww.Config()


@pytest.fixture
def temp_transcription_file() -> typing.Generator[str, None, None]:
    """Create temporary transcription file for tests."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        temp_file = f.name

    yield temp_file

    # Cleanup
    try:
        os.unlink(temp_file)
    except OSError:
        pass  # File may have been deleted by test
