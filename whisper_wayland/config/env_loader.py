"""Whisper Wayland - Environment Loader

Environment variable loading and .env file handling.
"""

import logging
import os
import typing

import dotenv

_logger = logging.getLogger(__name__)


class EnvLoaderError(Exception):
    """Raised when environment loading fails."""

    pass


class EnvLoader:
    """Handles loading environment variables from .env files."""

    def __init__(self) -> None:
        """Initialize environment loader."""
        pass

    def load_env_file(self, env_file: typing.Optional[str]) -> None:
        """Load environment variables from .env file if it exists.

        Args:
            env_file: Optional path to .env file to load

        Raises:
            EnvLoaderError: If environment file loading fails
        """
        try:
            if env_file:
                if os.path.exists(env_file):
                    dotenv.load_dotenv(env_file)
                    _logger.debug(f"Loaded environment from {env_file}")
                else:
                    _logger.warning(f"Environment file {env_file} not found")
            else:
                # Try to load from default locations
                for default_env in [".env", ".env.local"]:
                    if os.path.exists(default_env):
                        dotenv.load_dotenv(default_env)
                        _logger.debug(f"Loaded environment from {default_env}")
                        break
        except Exception as e:
            _logger.error(f"Failed to load environment file: {e}")
            raise EnvLoaderError(f"Environment file loading failed: {e}") from e

    @staticmethod
    def new() -> "EnvLoader":
        """Create environment loader instance.

        Returns:
            EnvLoader instance
        """
        return EnvLoader()
