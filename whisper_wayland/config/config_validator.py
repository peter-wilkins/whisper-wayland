"""Whisper Wayland - Config Validator

Configuration validation and requirement checking.
"""

import logging
import typing

_logger = logging.getLogger(__name__)


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""

    pass


class ConfigValidator:
    """Validates configuration requirements and constraints."""

    def __init__(self) -> None:
        """Initialize config validator."""
        pass

    def validate_required_config(self, config_instance: typing.Any) -> None:
        """Validate that all required configuration is present.

        Args:
            config_instance: Configuration instance to validate

        Raises:
            ConfigValidationError: If required configuration is missing
        """
        required_vars = ["OPENAI_API_KEY"]
        missing_vars = []

        for var in required_vars:
            if not getattr(config_instance, var.lower(), None):
                missing_vars.append(var)

        if missing_vars:
            error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
            _logger.error(error_msg)
            raise ConfigValidationError(error_msg)

    def get_safe_config_summary(self, config_instance: typing.Any) -> dict:
        """Get configuration summary with sensitive data masked.

        Args:
            config_instance: Configuration instance

        Returns:
            Dictionary with configuration summary
        """
        return {
            "openai_api_key": "***" if config_instance.openai_api_key else None,
            "whisper_model": config_instance.whisper_model,
            "transcription_request_timeout_secs": (
                config_instance.transcription_request_timeout_secs
            ),
            "transcription_max_retries": config_instance.transcription_max_retries,
            "audio_sample_rate": config_instance.audio_sample_rate,
            "audio_chunk_size": config_instance.audio_chunk_size,
            "audio_preroll_seconds": config_instance.audio_preroll_seconds,
            "audio_input_device_index": config_instance.audio_input_device_index,
            "audio_input_device_name": config_instance.audio_input_device_name,
            "max_recording_duration": config_instance.max_recording_duration,
            "audio_level_monitor_enabled": config_instance.audio_level_monitor_enabled,
            "audio_level_auto_adjust_enabled": (
                config_instance.audio_level_auto_adjust_enabled
            ),
            "audio_level_manage_mics_enabled": (
                config_instance.audio_level_manage_mics_enabled
            ),
            "audio_level_check_interval_secs": (
                config_instance.audio_level_check_interval_secs
            ),
            "audio_level_source": config_instance.audio_level_source,
            "audio_transcription_normalization_enabled": (
                config_instance.audio_transcription_normalization_enabled
            ),
            "audio_transcription_normalization_target_rms_dbfs": (
                config_instance.audio_transcription_normalization_target_rms_dbfs
            ),
            "audio_transcription_normalization_max_peak_amplitude": (
                config_instance.audio_transcription_normalization_max_peak_amplitude
            ),
            "audio_transcription_normalization_max_gain": (
                config_instance.audio_transcription_normalization_max_gain
            ),
            "log_level": config_instance.log_level,
            "hotkey": config_instance.hotkey,
            "hotkey_mode": config_instance.hotkey_mode,
            "streaming_transcription_enabled": config_instance.streaming_transcription_enabled,
            "streaming_transcription_model": config_instance.streaming_transcription_model,
            "streaming_sample_rate": config_instance.streaming_sample_rate,
            "streaming_completion_timeout_secs": config_instance.streaming_completion_timeout_secs,
            "streaming_delta_idle_timeout_secs": (
                config_instance.streaming_delta_idle_timeout_secs
            ),
            "streaming_turn_detection_enabled": (
                config_instance.streaming_turn_detection_enabled
            ),
            "streaming_vad_silence_duration_ms": (
                config_instance.streaming_vad_silence_duration_ms
            ),
            "text_insertion_delay": config_instance.text_insertion_delay,
            "text_insertion_method": config_instance.text_insertion_method,
            "text_tmux_target_pane": config_instance.text_tmux_target_pane,
            "text_paste_hotkey": config_instance.text_paste_hotkey,
            "text_post_process_mode": config_instance.text_post_process_mode,
            "text_post_process_model": config_instance.text_post_process_model,
            "text_post_process_providers": config_instance.text_post_process_providers,
            "text_post_process_local_api_url": (
                config_instance.text_post_process_local_api_url
            ),
            "text_post_process_local_api_timeout_secs": (
                config_instance.text_post_process_local_api_timeout_secs
            ),
            "continuum_capture_inlet_dir": config_instance.continuum_capture_inlet_dir,
        }

    @staticmethod
    def new() -> "ConfigValidator":
        """Create config validator instance.

        Returns:
            ConfigValidator instance
        """
        return ConfigValidator()
