"""Whisper Wayland - Audio System Validator

Audio system validation and device discovery functionality.
"""

import logging
import typing

import pyaudio

import whisper_wayland as ww

_logger = logging.getLogger(__name__)


class AudioSystemValidationError(Exception):
    """Raised when audio system validation fails."""

    pass


class AudioSystemValidator:
    """Validates audio system availability and configuration."""

    def __init__(self) -> None:
        """Initialize audio system validator."""
        pass

    def initialize_audio(self) -> pyaudio.PyAudio:
        """Initialize PyAudio instance with error handling.

        Returns:
            Initialized PyAudio instance

        Raises:
            AudioSystemValidationError: If PyAudio initialization fails
        """
        try:
            audio = pyaudio.PyAudio()
            _logger.debug("PyAudio initialized successfully")
            return audio
        except Exception as e:
            _logger.error(f"Failed to initialize PyAudio: {e}")
            raise AudioSystemValidationError(f"PyAudio initialization failed: {e}") from e

    def validate_audio_system(self, audio: pyaudio.PyAudio, config: "ww.Config") -> None:
        """Validate audio system availability and configuration.

        Args:
            audio: PyAudio instance
            config: Configuration instance

        Raises:
            AudioSystemValidationError: If audio system validation fails
        """
        try:
            # Check for available input devices
            device_count = audio.get_device_count()
            input_devices = []

            for i in range(device_count):
                device_info = audio.get_device_info_by_index(i)
                if device_info["maxInputChannels"] > 0:
                    input_devices.append(device_info)

            if not input_devices:
                raise AudioSystemValidationError("No audio input devices found")

            _logger.debug(f"Found {len(input_devices)} audio input devices")

            # Test audio format support with default input device
            try:
                default_device = audio.get_default_input_device_info()
                audio.is_format_supported(
                    rate=config.audio_sample_rate,
                    input_device=default_device["index"],
                    input_channels=1,
                    input_format=pyaudio.paInt16,
                )
                _logger.debug(
                    f"Audio format validated successfully for device: {default_device['name']}"
                )
            except (ValueError, OSError) as e:
                # Log as debug instead of warning since this is just a validation check
                # and the system can still work even if format validation fails
                _logger.debug(f"Audio format validation result: {e}")
            except Exception as e:
                _logger.debug(f"Could not validate audio format support: {e}")

        except Exception as e:
            _logger.error(f"Audio system validation failed: {e}")
            raise AudioSystemValidationError(f"Audio system validation failed: {e}") from e

    def find_preferred_input_device(
        self,
        audio: pyaudio.PyAudio,
        config: "ww.Config",
        warn_on_missing_explicit: bool = True,
    ) -> typing.Optional[int]:
        """Find the preferred input device.

        Explicitly configured devices are honored first. If an explicit device
        is unavailable, use the system default instead of guessing another
        external input; after suspend/resume stale USB inputs can stay listed
        while capturing near silence.

        Args:
            audio: PyAudio instance
            config: Configuration instance
            warn_on_missing_explicit: Log missing configured devices at warning level

        Returns:
            Device index of preferred device, or None to use the system default
        """
        explicit_index = config.audio_input_device_index
        explicit_device_requested = explicit_index is not None or bool(
            config.audio_input_device_name
        )

        if explicit_index is not None:
            if self._is_valid_input_device(audio, explicit_index):
                name = self.get_input_device_name(audio, explicit_index)
                _logger.info(f"Using configured input device: {name} (index {explicit_index})")
                return explicit_index
            self._log_missing_explicit_device(
                f"Configured AUDIO_INPUT_DEVICE_INDEX={explicit_index} is not a valid "
                "input device; using system default input device",
                warn_on_missing_explicit,
            )

        if explicit_index is None:
            explicit_name = config.audio_input_device_name
            if explicit_name:
                matched_index = self._find_input_device_by_name(audio, explicit_name)
                if matched_index is not None:
                    name = self.get_input_device_name(audio, matched_index)
                    _logger.info(f"Using configured input device: {name} (index {matched_index})")
                    return matched_index
                self._log_missing_explicit_device(
                    f"No input device matched AUDIO_INPUT_DEVICE_NAME='{explicit_name}'; "
                    "using system default input device",
                    warn_on_missing_explicit,
                )

        if explicit_device_requested:
            return self._use_system_default_input_device(audio)

        preferred_external_index = self._find_preferred_external_input_device(audio)
        if preferred_external_index is not None:
            return preferred_external_index

        _logger.debug("No USB/Bluetooth headset found, using system default input device")
        return None

    def _find_preferred_external_input_device(self, audio: pyaudio.PyAudio) -> int | None:
        """Return an auto-selected USB/Bluetooth input when no explicit device is set."""
        usb_keywords = ["usb"]
        bt_keywords = ["bluetooth", "bluez", "headset", "headphone"]
        candidates: dict[str, list[tuple[int, str]]] = {"usb": [], "bluetooth": []}

        try:
            for i in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(i)
                if info["maxInputChannels"] <= 0:
                    continue
                device_name = str(info["name"])
                normalized_name = device_name.lower()
                if any(k in normalized_name for k in usb_keywords):
                    candidates["usb"].append((i, device_name))
                elif any(k in normalized_name for k in bt_keywords):
                    candidates["bluetooth"].append((i, device_name))
        except Exception as e:
            _logger.warning(f"Error scanning audio devices: {e}")
            return None

        if candidates["usb"]:
            idx, name = candidates["usb"][0]
            _logger.info(f"Auto-selected USB input device: {name} (index {idx})")
            return idx
        if candidates["bluetooth"]:
            idx, name = candidates["bluetooth"][0]
            _logger.info(f"Auto-selected Bluetooth input device: {name} (index {idx})")
            return idx

        return None

    def _use_system_default_input_device(self, audio: pyaudio.PyAudio) -> None:
        """Log the current default input and return None for PyAudio default routing."""
        name = self.get_input_device_name(audio, None)
        _logger.info(f"Using system default input device: {name}")

    @staticmethod
    def _log_missing_explicit_device(message: str, warn: bool) -> None:
        """Log missing configured device once loudly, and refresh checks quietly."""
        if warn:
            _logger.warning(message)
        else:
            _logger.debug(message)

    def get_input_device_name(
        self, audio: pyaudio.PyAudio, input_device_index: typing.Optional[int]
    ) -> str:
        """Get display name for input device index or system default."""
        try:
            if input_device_index is None:
                info = audio.get_default_input_device_info()
                return str(info["name"])
            info = audio.get_device_info_by_index(input_device_index)
            return str(info["name"])
        except Exception as e:
            _logger.debug(f"Could not resolve input device name: {e}")
            return "system default"

    def _is_valid_input_device(self, audio: pyaudio.PyAudio, index: int) -> bool:
        """Return whether index refers to an available input device."""
        try:
            info = audio.get_device_info_by_index(index)
            return int(info["maxInputChannels"]) > 0
        except Exception:
            return False

    def _find_input_device_by_name(self, audio: pyaudio.PyAudio, name_match: str) -> int | None:
        """Find first input device whose name contains the configured substring."""
        try:
            for i in range(audio.get_device_count()):
                info = audio.get_device_info_by_index(i)
                if info["maxInputChannels"] <= 0:
                    continue
                if name_match in str(info["name"]).lower():
                    return i
        except Exception as e:
            _logger.warning(f"Error matching audio input device name: {e}")
        return None

    def get_audio_devices(self, audio: pyaudio.PyAudio) -> list[dict[str, typing.Any]]:
        """Get list of available audio input devices.

        Args:
            audio: PyAudio instance

        Returns:
            List of dictionaries containing device information
        """
        devices: list[dict[str, typing.Any]] = []

        try:
            device_count = audio.get_device_count()
            for i in range(device_count):
                device_info = audio.get_device_info_by_index(i)
                if device_info["maxInputChannels"] > 0:
                    devices.append(
                        {
                            "index": i,
                            "name": device_info["name"],
                            "channels": device_info["maxInputChannels"],
                            "sample_rate": device_info["defaultSampleRate"],
                        }
                    )
            _logger.debug(f"Retrieved {len(devices)} audio input devices")
        except Exception as e:
            _logger.error(f"Failed to get audio devices: {e}")

        return devices

    @staticmethod
    def new() -> "AudioSystemValidator":
        """Create audio system validator instance.

        Returns:
            AudioSystemValidator instance
        """
        return AudioSystemValidator()
