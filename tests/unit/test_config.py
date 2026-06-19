"""Whisper Wayland - Configuration Tests

Unit tests for configuration module functionality including
environment variable loading and validation."""

import os
import tempfile
import unittest.mock

import pytest

import whisper_wayland as ww

STREAMING_DEFAULT_SAMPLE_RATE = 24000
STREAMING_DEFAULT_TIMEOUT_SECS = 4
STREAMING_DEFAULT_DELTA_IDLE_TIMEOUT_SECS = 0.75
STREAMING_DEFAULT_VAD_SILENCE_MS = 700
STREAMING_CUSTOM_SAMPLE_RATE = 16000
STREAMING_CUSTOM_TIMEOUT_SECS = 3.5
STREAMING_CUSTOM_DELTA_IDLE_TIMEOUT_SECS = 0.5
STREAMING_CUSTOM_VAD_SILENCE_MS = 900
CUSTOM_AUDIO_INPUT_DEVICE_INDEX = 3
DEFAULT_AUDIO_PREROLL_SECONDS = 1.0
CUSTOM_AUDIO_PREROLL_SECONDS = 2.5
DEFAULT_AUDIO_LEVEL_CHECK_INTERVAL_SECS = 900
CUSTOM_AUDIO_LEVEL_CHECK_INTERVAL_SECS = 30
DEFAULT_NORMALIZATION_TARGET_RMS_DBFS = -22
DEFAULT_NORMALIZATION_MAX_PEAK_AMPLITUDE = 0.95
DEFAULT_NORMALIZATION_MAX_GAIN = 6
CUSTOM_NORMALIZATION_TARGET_RMS_DBFS = -24
CUSTOM_NORMALIZATION_MAX_PEAK_AMPLITUDE = 0.9
CUSTOM_NORMALIZATION_MAX_GAIN = 4
DEFAULT_TEXT_POST_PROCESS_PROVIDERS = ["openai", "local"]
CUSTOM_TEXT_POST_PROCESS_PROVIDERS = ["local-api", "openai", "local"]
DEFAULT_TEXT_POST_PROCESS_LOCAL_API_URL = "http://127.0.0.1:8765/v1/transcript/rewrite"
CUSTOM_TEXT_POST_PROCESS_LOCAL_API_URL = "http://127.0.0.1:9999/v1/transcript/rewrite"
DEFAULT_TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS = 1.5
CUSTOM_TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS = 0.75
DEFAULT_TRANSCRIPTION_REQUEST_TIMEOUT_SECS = 20
CUSTOM_TRANSCRIPTION_REQUEST_TIMEOUT_SECS = 8.5
DEFAULT_TRANSCRIPTION_MAX_RETRIES = 1
CUSTOM_TRANSCRIPTION_MAX_RETRIES = 0
DEFAULT_TRANSCRIPTION_RACE_MODELS: list[str] = []
CUSTOM_TRANSCRIPTION_RACE_MODELS = ["gpt-4o-mini-transcribe", "whisper-1"]
DEFAULT_TRANSCRIPTION_VAD_AUTO_MIN_DURATION_SECONDS = 30
CUSTOM_TRANSCRIPTION_VAD_AUTO_MIN_DURATION_SECONDS = 45.5
DEFAULT_PRETRANSCRIPTION_CHUNK_WHISPER_MODEL = "whisper-1"
DEFAULT_PRETRANSCRIPTION_CHUNK_RACE_MODELS: list[str] = []
DEFAULT_PRETRANSCRIPTION_CHUNK_MIN_RECORDING_SECONDS = 10
DEFAULT_PRETRANSCRIPTION_CHUNK_POLL_INTERVAL_SECONDS = 2
DEFAULT_PRETRANSCRIPTION_CHUNK_STABLE_TAIL_SECONDS = 3
DEFAULT_PRETRANSCRIPTION_CHUNK_COALESCE_MIN_DURATION_SECONDS = 4
DEFAULT_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_DURATION_SECONDS = 12
DEFAULT_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_GAP_SECONDS = 3
CUSTOM_PRETRANSCRIPTION_CHUNK_WHISPER_MODEL = "gpt-4o-transcribe"
CUSTOM_PRETRANSCRIPTION_CHUNK_RACE_MODELS = ["whisper-1", "deepgram:nova-3"]
CUSTOM_PRETRANSCRIPTION_CHUNK_MIN_RECORDING_SECONDS = 11
CUSTOM_PRETRANSCRIPTION_CHUNK_POLL_INTERVAL_SECONDS = 2.5
CUSTOM_PRETRANSCRIPTION_CHUNK_STABLE_TAIL_SECONDS = 3.5
CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MIN_DURATION_SECONDS = 4.5
CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_DURATION_SECONDS = 13
CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_GAP_SECONDS = 3.5


class TestConfig:
    """Test cases for Config class."""

    def test_config_initialization_with_defaults(self) -> None:  # noqa: PLR0915
        """Test config initialization with default values."""
        # Temporarily remove LOG_LEVEL to test default
        old_log_level = os.environ.pop("LOG_LEVEL", None)
        try:
            with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
                test_config = ww.Config("/nonexistent/test.env")

                assert test_config.openai_api_key == "sk-test123"
                assert test_config.deepgram_api_key == ""
                assert test_config.whisper_model == "gpt-4o-transcribe"
                assert (
                    test_config.transcription_request_timeout_secs
                    == DEFAULT_TRANSCRIPTION_REQUEST_TIMEOUT_SECS
                )
                assert test_config.transcription_max_retries == DEFAULT_TRANSCRIPTION_MAX_RETRIES
                assert test_config.transcription_race_models == DEFAULT_TRANSCRIPTION_RACE_MODELS
                assert (
                    test_config.transcription_vad_auto_min_duration_seconds
                    == DEFAULT_TRANSCRIPTION_VAD_AUTO_MIN_DURATION_SECONDS
                )
                assert test_config.audio_transcription_vad_mode == "auto"
                assert test_config.local_api_default_vad_mode == "auto"
                assert (
                    test_config.pretranscription_chunk_whisper_model
                    == DEFAULT_PRETRANSCRIPTION_CHUNK_WHISPER_MODEL
                )
                assert (
                    test_config.pretranscription_chunk_race_models
                    == DEFAULT_PRETRANSCRIPTION_CHUNK_RACE_MODELS
                )
                assert not test_config.pretranscription_chunking_enabled
                assert (
                    test_config.pretranscription_chunk_min_recording_seconds
                    == DEFAULT_PRETRANSCRIPTION_CHUNK_MIN_RECORDING_SECONDS
                )
                assert (
                    test_config.pretranscription_chunk_poll_interval_seconds
                    == DEFAULT_PRETRANSCRIPTION_CHUNK_POLL_INTERVAL_SECONDS
                )
                assert (
                    test_config.pretranscription_chunk_stable_tail_seconds
                    == DEFAULT_PRETRANSCRIPTION_CHUNK_STABLE_TAIL_SECONDS
                )
                assert (
                    test_config.pretranscription_chunk_coalesce_min_duration_seconds
                    == DEFAULT_PRETRANSCRIPTION_CHUNK_COALESCE_MIN_DURATION_SECONDS
                )
                assert (
                    test_config.pretranscription_chunk_coalesce_max_duration_seconds
                    == DEFAULT_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_DURATION_SECONDS
                )
                assert (
                    test_config.pretranscription_chunk_coalesce_max_gap_seconds
                    == DEFAULT_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_GAP_SECONDS
                )
                assert test_config.audio_sample_rate == ww.Constants.DEFAULT_SAMPLE_RATE
                assert test_config.audio_chunk_size == ww.Constants.DEFAULT_CHUNK_SIZE
                assert test_config.audio_preroll_seconds == DEFAULT_AUDIO_PREROLL_SECONDS
                assert test_config.audio_input_device_index is None
                assert test_config.audio_input_device_name == ""
                assert test_config.max_recording_duration == ww.Constants.DEFAULT_RECORDING_DURATION
                assert not test_config.audio_level_monitor_enabled
                assert not test_config.audio_level_auto_adjust_enabled
                assert not test_config.audio_level_manage_mics_enabled
                assert (
                    test_config.audio_level_check_interval_secs
                    == DEFAULT_AUDIO_LEVEL_CHECK_INTERVAL_SECS
                )
                assert test_config.audio_level_source == "@DEFAULT_SOURCE@"
                assert not test_config.audio_transcription_normalization_enabled
                assert (
                    test_config.audio_transcription_normalization_target_rms_dbfs
                    == DEFAULT_NORMALIZATION_TARGET_RMS_DBFS
                )
                assert (
                    test_config.audio_transcription_normalization_max_peak_amplitude
                    == DEFAULT_NORMALIZATION_MAX_PEAK_AMPLITUDE
                )
                assert (
                    test_config.audio_transcription_normalization_max_gain
                    == DEFAULT_NORMALIZATION_MAX_GAIN
                )
                assert test_config.log_level == "INFO"
                assert test_config.hotkey == "ctrl+compose"
                assert test_config.hotkey_mode == "push_to_talk"
                assert test_config.text_tmux_target_pane == ""
                assert test_config.text_paste_hotkey == "ctrl+v"
                assert not test_config.text_insertion_marker_enabled
                assert test_config.text_post_process_openai_api_key == ""
                assert (
                    test_config.text_post_process_providers == DEFAULT_TEXT_POST_PROCESS_PROVIDERS
                )
                assert (
                    test_config.text_post_process_local_api_url
                    == DEFAULT_TEXT_POST_PROCESS_LOCAL_API_URL
                )
                assert (
                    test_config.text_post_process_local_api_timeout_secs
                    == DEFAULT_TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS
                )
                assert test_config.continuum_capture_inlet_dir == ""
                assert not test_config.streaming_transcription_enabled
                assert test_config.streaming_transcription_model == "gpt-realtime-whisper"
                assert test_config.streaming_sample_rate == STREAMING_DEFAULT_SAMPLE_RATE
                assert (
                    test_config.streaming_completion_timeout_secs == STREAMING_DEFAULT_TIMEOUT_SECS
                )
                assert (
                    test_config.streaming_delta_idle_timeout_secs
                    == STREAMING_DEFAULT_DELTA_IDLE_TIMEOUT_SECS
                )
                assert not test_config.streaming_turn_detection_enabled
                assert (
                    test_config.streaming_vad_silence_duration_ms
                    == STREAMING_DEFAULT_VAD_SILENCE_MS
                )
        finally:
            # Restore LOG_LEVEL if it existed
            if old_log_level:
                os.environ["LOG_LEVEL"] = old_log_level

    def test_config_missing_required_api_key(self) -> None:
        """Test config fails when required API key is missing."""
        # Temporarily remove API key to test validation
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with pytest.raises(ww.ConfigError, match="OPENAI_API_KEY"):
                ww.Config()

    def test_config_empty_api_key(self) -> None:
        """Test config fails when API key is empty."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": ""}):
            with pytest.raises(ww.ConfigError, match="OPENAI_API_KEY"):
                ww.Config()

    def test_config_custom_values(self) -> None:  # noqa: PLR0915
        """Test config with custom environment values."""
        env_vars = {
            "OPENAI_API_KEY": "sk-custom123",
            "DEEPGRAM_API_KEY": "dg-custom123",
            "WHISPER_MODEL": "large",
            "TRANSCRIPTION_REQUEST_TIMEOUT_SECS": str(CUSTOM_TRANSCRIPTION_REQUEST_TIMEOUT_SECS),
            "TRANSCRIPTION_MAX_RETRIES": str(CUSTOM_TRANSCRIPTION_MAX_RETRIES),
            "TRANSCRIPTION_RACE_MODELS": "gpt-4o-mini-transcribe, whisper-1",
            "TRANSCRIPTION_VAD_AUTO_MIN_DURATION_SECONDS": str(
                CUSTOM_TRANSCRIPTION_VAD_AUTO_MIN_DURATION_SECONDS
            ),
            "AUDIO_TRANSCRIPTION_VAD_MODE": "none",
            "LOCAL_API_DEFAULT_VAD_MODE": "silero",
            "PRETRANSCRIPTION_CHUNK_WHISPER_MODEL": (CUSTOM_PRETRANSCRIPTION_CHUNK_WHISPER_MODEL),
            "PRETRANSCRIPTION_CHUNK_RACE_MODELS": "whisper-1, deepgram:nova-3",
            "PRETRANSCRIPTION_CHUNKING_ENABLED": "true",
            "PRETRANSCRIPTION_CHUNK_MIN_RECORDING_SECONDS": str(
                CUSTOM_PRETRANSCRIPTION_CHUNK_MIN_RECORDING_SECONDS
            ),
            "PRETRANSCRIPTION_CHUNK_POLL_INTERVAL_SECONDS": str(
                CUSTOM_PRETRANSCRIPTION_CHUNK_POLL_INTERVAL_SECONDS
            ),
            "PRETRANSCRIPTION_CHUNK_STABLE_TAIL_SECONDS": str(
                CUSTOM_PRETRANSCRIPTION_CHUNK_STABLE_TAIL_SECONDS
            ),
            "PRETRANSCRIPTION_CHUNK_COALESCE_MIN_DURATION_SECONDS": str(
                CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MIN_DURATION_SECONDS
            ),
            "PRETRANSCRIPTION_CHUNK_COALESCE_MAX_DURATION_SECONDS": str(
                CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_DURATION_SECONDS
            ),
            "PRETRANSCRIPTION_CHUNK_COALESCE_MAX_GAP_SECONDS": str(
                CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_GAP_SECONDS
            ),
            "AUDIO_SAMPLE_RATE": "44100",
            "AUDIO_CHUNK_SIZE": "2048",
            "AUDIO_PREROLL_SECONDS": str(CUSTOM_AUDIO_PREROLL_SECONDS),
            "AUDIO_INPUT_DEVICE_INDEX": str(CUSTOM_AUDIO_INPUT_DEVICE_INDEX),
            "AUDIO_INPUT_DEVICE_NAME": "rode",
            "AUDIO_LEVEL_MONITOR_ENABLED": "true",
            "AUDIO_LEVEL_AUTO_ADJUST_ENABLED": "true",
            "AUDIO_LEVEL_MANAGE_MICS_ENABLED": "true",
            "AUDIO_LEVEL_CHECK_INTERVAL_SECS": str(CUSTOM_AUDIO_LEVEL_CHECK_INTERVAL_SECS),
            "AUDIO_LEVEL_SOURCE": "alsa_input.pci",
            "AUDIO_TRANSCRIPTION_NORMALIZATION_ENABLED": "true",
            "AUDIO_TRANSCRIPTION_NORMALIZATION_TARGET_RMS_DBFS": str(
                CUSTOM_NORMALIZATION_TARGET_RMS_DBFS
            ),
            "AUDIO_TRANSCRIPTION_NORMALIZATION_MAX_PEAK_AMPLITUDE": str(
                CUSTOM_NORMALIZATION_MAX_PEAK_AMPLITUDE
            ),
            "AUDIO_TRANSCRIPTION_NORMALIZATION_MAX_GAIN": str(CUSTOM_NORMALIZATION_MAX_GAIN),
            "MAX_RECORDING_DURATION": "60",
            "LOG_LEVEL": "DEBUG",
            "HOTKEY": "alt+space",
            "HOTKEY_MODE": "toggle",
            "TEXT_TMUX_TARGET_PANE": "whisper-wayland:0.0",
            "TEXT_PASTE_HOTKEY": "ctrl+shift+v",
            "TEXT_INSERTION_MARKER_ENABLED": "true",
            "TEXT_POST_PROCESS_MODE": "snappy",
            "TEXT_POST_PROCESS_MODEL": "gpt-test-model",
            "TEXT_POST_PROCESS_PROVIDERS": "local-api, openai, local",
            "TEXT_POST_PROCESS_LOCAL_API_URL": CUSTOM_TEXT_POST_PROCESS_LOCAL_API_URL,
            "TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS": str(
                CUSTOM_TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS
            ),
            "CONTINUUM_CAPTURE_INLET_DIR": "/tmp/continuum/audio",
            "STREAMING_TRANSCRIPTION_ENABLED": "true",
            "STREAMING_TRANSCRIPTION_MODEL": "whisper-1",
            "STREAMING_SAMPLE_RATE": "16000",
            "STREAMING_COMPLETION_TIMEOUT_SECS": "3.5",
            "STREAMING_DELTA_IDLE_TIMEOUT_SECS": "0.5",
            "STREAMING_TURN_DETECTION_ENABLED": "true",
            "STREAMING_VAD_SILENCE_DURATION_MS": str(STREAMING_CUSTOM_VAD_SILENCE_MS),
        }

        with unittest.mock.patch.dict(os.environ, env_vars):
            test_config = ww.Config("/nonexistent/test.env")

            assert test_config.openai_api_key == "sk-custom123"
            assert test_config.deepgram_api_key == "dg-custom123"
            assert test_config.whisper_model == "large"
            assert (
                test_config.transcription_request_timeout_secs
                == CUSTOM_TRANSCRIPTION_REQUEST_TIMEOUT_SECS
            )
            assert test_config.transcription_max_retries == CUSTOM_TRANSCRIPTION_MAX_RETRIES
            assert test_config.transcription_race_models == CUSTOM_TRANSCRIPTION_RACE_MODELS
            assert (
                test_config.transcription_vad_auto_min_duration_seconds
                == CUSTOM_TRANSCRIPTION_VAD_AUTO_MIN_DURATION_SECONDS
            )
            assert test_config.audio_transcription_vad_mode == "none"
            assert test_config.local_api_default_vad_mode == "silero"
            assert (
                test_config.pretranscription_chunk_whisper_model
                == CUSTOM_PRETRANSCRIPTION_CHUNK_WHISPER_MODEL
            )
            assert (
                test_config.pretranscription_chunk_race_models
                == CUSTOM_PRETRANSCRIPTION_CHUNK_RACE_MODELS
            )
            assert test_config.pretranscription_chunking_enabled
            assert (
                test_config.pretranscription_chunk_min_recording_seconds
                == CUSTOM_PRETRANSCRIPTION_CHUNK_MIN_RECORDING_SECONDS
            )
            assert (
                test_config.pretranscription_chunk_poll_interval_seconds
                == CUSTOM_PRETRANSCRIPTION_CHUNK_POLL_INTERVAL_SECONDS
            )
            assert (
                test_config.pretranscription_chunk_stable_tail_seconds
                == CUSTOM_PRETRANSCRIPTION_CHUNK_STABLE_TAIL_SECONDS
            )
            assert (
                test_config.pretranscription_chunk_coalesce_min_duration_seconds
                == CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MIN_DURATION_SECONDS
            )
            assert (
                test_config.pretranscription_chunk_coalesce_max_duration_seconds
                == CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_DURATION_SECONDS
            )
            assert (
                test_config.pretranscription_chunk_coalesce_max_gap_seconds
                == CUSTOM_PRETRANSCRIPTION_CHUNK_COALESCE_MAX_GAP_SECONDS
            )
            assert test_config.audio_sample_rate == ww.Constants.HIGH_QUALITY_SAMPLE_RATE
            assert test_config.audio_chunk_size == ww.Constants.LARGE_CHUNK_SIZE
            assert test_config.audio_preroll_seconds == CUSTOM_AUDIO_PREROLL_SECONDS
            assert test_config.audio_input_device_index == CUSTOM_AUDIO_INPUT_DEVICE_INDEX
            assert test_config.audio_input_device_name == "rode"
            assert test_config.max_recording_duration == ww.Constants.LONG_RECORDING_DURATION
            assert test_config.audio_level_monitor_enabled
            assert test_config.audio_level_auto_adjust_enabled
            assert test_config.audio_level_manage_mics_enabled
            assert (
                test_config.audio_level_check_interval_secs
                == CUSTOM_AUDIO_LEVEL_CHECK_INTERVAL_SECS
            )
            assert test_config.audio_level_source == "alsa_input.pci"
            assert test_config.audio_transcription_normalization_enabled
            assert (
                test_config.audio_transcription_normalization_target_rms_dbfs
                == CUSTOM_NORMALIZATION_TARGET_RMS_DBFS
            )
            assert (
                test_config.audio_transcription_normalization_max_peak_amplitude
                == CUSTOM_NORMALIZATION_MAX_PEAK_AMPLITUDE
            )
            assert (
                test_config.audio_transcription_normalization_max_gain
                == CUSTOM_NORMALIZATION_MAX_GAIN
            )
            assert test_config.log_level == "DEBUG"
            assert test_config.hotkey == "alt+space"
            assert test_config.hotkey_mode == "toggle"
            assert test_config.text_tmux_target_pane == "whisper-wayland:0.0"
            assert test_config.text_paste_hotkey == "ctrl+shift+v"
            assert test_config.text_insertion_marker_enabled
            assert test_config.text_post_process_mode == "snappy"
            assert test_config.text_post_process_model == "gpt-test-model"
            assert test_config.text_post_process_providers == CUSTOM_TEXT_POST_PROCESS_PROVIDERS
            assert (
                test_config.text_post_process_local_api_url
                == CUSTOM_TEXT_POST_PROCESS_LOCAL_API_URL
            )
            assert (
                test_config.text_post_process_local_api_timeout_secs
                == CUSTOM_TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS
            )
            assert test_config.continuum_capture_inlet_dir == "/tmp/continuum/audio"
            assert test_config.streaming_transcription_enabled
            assert test_config.streaming_transcription_model == "whisper-1"
            assert test_config.streaming_sample_rate == STREAMING_CUSTOM_SAMPLE_RATE
            assert test_config.streaming_completion_timeout_secs == STREAMING_CUSTOM_TIMEOUT_SECS
            assert (
                test_config.streaming_delta_idle_timeout_secs
                == STREAMING_CUSTOM_DELTA_IDLE_TIMEOUT_SECS
            )
            assert test_config.streaming_turn_detection_enabled
            assert test_config.streaming_vad_silence_duration_ms == STREAMING_CUSTOM_VAD_SILENCE_MS

    def test_config_invalid_hotkey_mode(self) -> None:
        """Test config handles invalid hotkey modes gracefully."""
        with unittest.mock.patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-test123", "HOTKEY_MODE": "invalid"}
        ):
            test_config = ww.Config("/nonexistent/test.env")
            assert test_config.hotkey_mode == "push_to_talk"

    def test_config_invalid_numeric_values(self) -> None:
        """Test config validation of numeric values."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            # Invalid sample rate
            with unittest.mock.patch.dict(os.environ, {"AUDIO_SAMPLE_RATE": "invalid"}):
                with pytest.raises(ww.ConfigError, match="AUDIO_SAMPLE_RATE"):
                    ww.Config()

            # Negative sample rate
            with unittest.mock.patch.dict(os.environ, {"AUDIO_SAMPLE_RATE": "-1000"}):
                with pytest.raises(ww.ConfigError, match="AUDIO_SAMPLE_RATE"):
                    ww.Config()

            # Invalid chunk size
            with unittest.mock.patch.dict(os.environ, {"AUDIO_CHUNK_SIZE": "not_a_number"}):
                with pytest.raises(ww.ConfigError, match="AUDIO_CHUNK_SIZE"):
                    ww.Config()

            # Invalid audio pre-roll
            with unittest.mock.patch.dict(os.environ, {"AUDIO_PREROLL_SECONDS": "-1"}):
                with pytest.raises(ww.ConfigError, match="AUDIO_PREROLL_SECONDS"):
                    ww.Config()

            # Excessive audio pre-roll
            with unittest.mock.patch.dict(os.environ, {"AUDIO_PREROLL_SECONDS": "4"}):
                with pytest.raises(ww.ConfigError, match="AUDIO_PREROLL_SECONDS"):
                    ww.Config()

            # Invalid input device index
            with unittest.mock.patch.dict(os.environ, {"AUDIO_INPUT_DEVICE_INDEX": "invalid"}):
                with pytest.raises(ww.ConfigError, match="AUDIO_INPUT_DEVICE_INDEX"):
                    ww.Config()

            # Negative input device index
            with unittest.mock.patch.dict(os.environ, {"AUDIO_INPUT_DEVICE_INDEX": "-1"}):
                with pytest.raises(ww.ConfigError, match="AUDIO_INPUT_DEVICE_INDEX"):
                    ww.Config()

            # Invalid recording duration
            with unittest.mock.patch.dict(os.environ, {"MAX_RECORDING_DURATION": "zero"}):
                with pytest.raises(ww.ConfigError, match="MAX_RECORDING_DURATION"):
                    ww.Config()

            # Invalid audio level check interval
            with unittest.mock.patch.dict(os.environ, {"AUDIO_LEVEL_CHECK_INTERVAL_SECS": "-1"}):
                with pytest.raises(ww.ConfigError, match="AUDIO_LEVEL_CHECK_INTERVAL_SECS"):
                    ww.Config()

            # Non-negative transcription normalization target
            with unittest.mock.patch.dict(
                os.environ,
                {"AUDIO_TRANSCRIPTION_NORMALIZATION_TARGET_RMS_DBFS": "1"},
            ):
                with pytest.raises(
                    ww.ConfigError,
                    match="AUDIO_TRANSCRIPTION_NORMALIZATION_TARGET_RMS_DBFS",
                ):
                    ww.Config()

            # Invalid transcription normalization peak limit
            with unittest.mock.patch.dict(
                os.environ,
                {"AUDIO_TRANSCRIPTION_NORMALIZATION_MAX_PEAK_AMPLITUDE": "2"},
            ):
                with pytest.raises(
                    ww.ConfigError,
                    match="AUDIO_TRANSCRIPTION_NORMALIZATION_MAX_PEAK_AMPLITUDE",
                ):
                    ww.Config()

            # Invalid streaming sample rate
            with unittest.mock.patch.dict(os.environ, {"STREAMING_SAMPLE_RATE": "invalid"}):
                with pytest.raises(ww.ConfigError, match="STREAMING_SAMPLE_RATE"):
                    ww.Config()

            # Invalid streaming timeout
            with unittest.mock.patch.dict(os.environ, {"STREAMING_COMPLETION_TIMEOUT_SECS": "-1"}):
                with pytest.raises(ww.ConfigError, match="STREAMING_COMPLETION_TIMEOUT_SECS"):
                    ww.Config()

            # Invalid streaming VAD silence duration
            with unittest.mock.patch.dict(os.environ, {"STREAMING_VAD_SILENCE_DURATION_MS": "0"}):
                with pytest.raises(ww.ConfigError, match="STREAMING_VAD_SILENCE_DURATION_MS"):
                    ww.Config()

            # Invalid local post-process API timeout
            with unittest.mock.patch.dict(
                os.environ,
                {"TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS": "0"},
            ):
                with pytest.raises(
                    ww.ConfigError,
                    match="TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS",
                ):
                    ww.Config()

    def test_config_invalid_transcription_timeout_values(self) -> None:
        """Test config validation of transcription timeout values."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            with unittest.mock.patch.dict(
                os.environ,
                {"TRANSCRIPTION_REQUEST_TIMEOUT_SECS": "0"},
            ):
                with pytest.raises(
                    ww.ConfigError,
                    match="TRANSCRIPTION_REQUEST_TIMEOUT_SECS",
                ):
                    ww.Config()

            with unittest.mock.patch.dict(
                os.environ,
                {"TRANSCRIPTION_MAX_RETRIES": "-1"},
            ):
                with pytest.raises(ww.ConfigError, match="TRANSCRIPTION_MAX_RETRIES"):
                    ww.Config()

    def test_config_invalid_log_level(self) -> None:
        """Test config handles invalid log levels gracefully."""
        with unittest.mock.patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-test123", "LOG_LEVEL": "INVALID_LEVEL"}
        ):
            test_config = ww.Config("/nonexistent/test.env")
            assert test_config.log_level == "INFO"  # Should fallback to default

    def test_config_text_insertion_delay(self) -> None:
        """Test text insertion delay configuration."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            # Default value
            test_config = ww.Config("/nonexistent/test.env")
            assert test_config.text_insertion_delay == ww.Constants.DEFAULT_TEXT_INSERTION_DELAY

            # Custom value
            with unittest.mock.patch.dict(os.environ, {"TEXT_INSERTION_DELAY": "0.5"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_insertion_delay == ww.Constants.CUSTOM_TEXT_INSERTION_DELAY

            # Invalid value
            with unittest.mock.patch.dict(os.environ, {"TEXT_INSERTION_DELAY": "invalid"}):
                with pytest.raises(ww.ConfigError, match="TEXT_INSERTION_DELAY"):
                    ww.Config("/nonexistent/test.env")

            # Negative value
            with unittest.mock.patch.dict(os.environ, {"TEXT_INSERTION_DELAY": "-1.0"}):
                with pytest.raises(ww.ConfigError, match="TEXT_INSERTION_DELAY"):
                    ww.Config("/nonexistent/test.env")

    def test_config_text_insertion_method(self) -> None:
        """Test text insertion method configuration."""
        # Temporarily remove TEXT_INSERTION_METHOD to test default
        old_method = os.environ.pop("TEXT_INSERTION_METHOD", None)
        try:
            with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_insertion_method == "auto"

                # Valid custom value
                with unittest.mock.patch.dict(os.environ, {"TEXT_INSERTION_METHOD": "xdotool"}):
                    test_config = ww.Config("/nonexistent/test.env")
                    assert test_config.text_insertion_method == "xdotool"

                with unittest.mock.patch.dict(os.environ, {"TEXT_INSERTION_METHOD": "auto"}):
                    test_config = ww.Config("/nonexistent/test.env")
                    assert test_config.text_insertion_method == "auto"
        finally:
            # Restore TEXT_INSERTION_METHOD if it existed
            if old_method:
                os.environ["TEXT_INSERTION_METHOD"] = old_method

        # Test after restoring to ensure proper cleanup
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            # Invalid value (should fallback to default)
            with unittest.mock.patch.dict(os.environ, {"TEXT_INSERTION_METHOD": "invalid_method"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_insertion_method == "auto"

    def test_config_text_paste_hotkey(self) -> None:
        """Test paste hotkey configuration."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            test_config = ww.Config("/nonexistent/test.env")
            assert test_config.text_paste_hotkey == "ctrl+v"

            with unittest.mock.patch.dict(os.environ, {"TEXT_PASTE_HOTKEY": "ctrl+shift+v"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_paste_hotkey == "ctrl+shift+v"

            with unittest.mock.patch.dict(os.environ, {"TEXT_PASTE_HOTKEY": "invalid"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_paste_hotkey == "ctrl+v"

            with unittest.mock.patch.dict(os.environ, {"TEXT_INSERTION_METHOD": "tmux"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_insertion_method == "tmux"

    def test_config_text_post_process_mode(self) -> None:
        """Test text post-processing mode configuration."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}, clear=True):
            test_config = ww.Config("/nonexistent/test.env")
            assert test_config.text_post_process_mode == "raw"
            assert test_config.text_post_process_model == "gpt-4.1-mini"

            with unittest.mock.patch.dict(os.environ, {"TEXT_POST_PROCESS_MODE": "clean"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_post_process_mode == "clean"

            with unittest.mock.patch.dict(os.environ, {"TEXT_POST_PROCESS_MODE": "caveman"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_post_process_mode == "caveman"

            with unittest.mock.patch.dict(os.environ, {"TEXT_POST_PROCESS_MODE": "extract"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_post_process_mode == "extract"

            with unittest.mock.patch.dict(os.environ, {"TEXT_POST_PROCESS_MODE": "invalid"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_post_process_mode == "raw"

            with unittest.mock.patch.dict(os.environ, {"TEXT_POST_PROCESS_MODEL": "gpt-test"}):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_post_process_model == "gpt-test"

            with unittest.mock.patch.dict(
                os.environ,
                {"TEXT_POST_PROCESS_OPENAI_API_KEY": "sk-rewrite-test"},
            ):
                test_config = ww.Config("/nonexistent/test.env")
                assert test_config.text_post_process_openai_api_key == "sk-rewrite-test"

    def test_config_load_env_file(self) -> None:
        """Test loading configuration from .env file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("OPENAI_API_KEY=sk-envfile123\n")
            f.write("WHISPER_MODEL=small\n")
            f.write("LOG_LEVEL=DEBUG\n")
            env_file_path = f.name

        # Temporarily remove environment variables that would override .env file
        old_api_key = os.environ.pop("OPENAI_API_KEY", None)
        old_model = os.environ.pop("WHISPER_MODEL", None)
        old_log_level = os.environ.pop("LOG_LEVEL", None)

        try:
            test_config = ww.Config(env_file_path)
            assert test_config.openai_api_key == "sk-envfile123"
            assert test_config.whisper_model == "small"
            assert test_config.log_level == "DEBUG"
        finally:
            # Restore environment variables
            if old_api_key:
                os.environ["OPENAI_API_KEY"] = old_api_key
            if old_model:
                os.environ["WHISPER_MODEL"] = old_model
            if old_log_level:
                os.environ["LOG_LEVEL"] = old_log_level
            os.unlink(env_file_path)

    def test_config_load_nonexistent_env_file(self) -> None:
        """Test handling of nonexistent .env file."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            # Should not raise an error, just log a warning
            test_config = ww.Config("/nonexistent/file.env")
            assert test_config.openai_api_key == "sk-test123"

    def test_config_safe_summary(self) -> None:
        """Test safe configuration summary masks sensitive data."""
        with unittest.mock.patch.dict(
            os.environ, {"OPENAI_API_KEY": "sk-sensitive123"}, clear=True
        ):
            test_config = ww.Config("/nonexistent/test.env")
            summary = test_config._get_safe_config_summary()

            assert summary["openai_api_key"] == "***"
            assert summary["whisper_model"] == "gpt-4o-transcribe"
            assert summary["audio_preroll_seconds"] == DEFAULT_AUDIO_PREROLL_SECONDS
            assert summary["continuum_capture_inlet_dir"] == ""
            assert summary["audio_level_monitor_enabled"] is False
            assert summary["audio_level_manage_mics_enabled"] is False
            assert summary["audio_transcription_normalization_enabled"] is False
            assert summary["text_insertion_marker_enabled"] is False
            assert summary["text_post_process_providers"] == DEFAULT_TEXT_POST_PROCESS_PROVIDERS
            assert summary["text_post_process_openai_api_key"] is None
            assert (
                summary["pretranscription_chunk_whisper_model"]
                == DEFAULT_PRETRANSCRIPTION_CHUNK_WHISPER_MODEL
            )
            assert (
                summary["pretranscription_chunk_race_models"]
                == DEFAULT_PRETRANSCRIPTION_CHUNK_RACE_MODELS
            )
            assert (
                summary["text_post_process_local_api_url"]
                == DEFAULT_TEXT_POST_PROCESS_LOCAL_API_URL
            )
            assert (
                summary["text_post_process_local_api_timeout_secs"]
                == DEFAULT_TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS
            )
            assert "sk-sensitive123" not in str(summary)

    def test_config_get_static_method(self) -> None:
        """Test Config.get static method."""
        with unittest.mock.patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            test_config = ww.Config.get()
            assert isinstance(test_config, ww.Config)
            assert test_config.openai_api_key == "sk-test123"

    def test_config_get_with_file(self) -> None:
        """Test Config.get with environment file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as f:
            f.write("OPENAI_API_KEY=sk-filetest123\n")
            env_file_path = f.name

        # Temporarily remove environment variable to test .env file loading
        old_api_key = os.environ.pop("OPENAI_API_KEY", None)

        try:
            test_config = ww.Config.get(env_file_path)
            assert test_config.openai_api_key == "sk-filetest123"
        finally:
            # Restore environment variable
            if old_api_key:
                os.environ["OPENAI_API_KEY"] = old_api_key
            os.unlink(env_file_path)
