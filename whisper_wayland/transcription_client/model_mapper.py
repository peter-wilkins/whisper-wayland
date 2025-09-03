"""Whisper Wayland - Model Mapper

Maps model names between configuration and OpenAI API formats.
"""

import logging

_logger = logging.getLogger(__name__)


class ModelMapper:
    """Maps model names between configuration and API formats."""

    def __init__(self) -> None:
        """Initialize model mapper."""
        pass

    def map_model_name(self, model: str) -> str:
        """Map configuration model name to OpenAI API model name.

        Args:
            model: Model name from configuration

        Returns:
            API-compatible model name
        """
        # For OpenAI API, the main model is called "whisper-1"
        # Local model names are mapped to this
        model_mapping = {
            "tiny": "whisper-1",
            "base": "whisper-1",
            "small": "whisper-1",
            "medium": "whisper-1",
            "large": "whisper-1",
            "large-v2": "whisper-1",
            "large-v3": "whisper-1",
            "whisper-1": "whisper-1",
        }

        api_model = model_mapping.get(model, "whisper-1")
        if api_model != model:
            _logger.debug(f"Mapped model '{model}' to API model '{api_model}'")

        return api_model

    @staticmethod
    def new() -> "ModelMapper":
        """Create model mapper instance.

        Returns:
            ModelMapper instance
        """
        return ModelMapper()
