"""Whisper Wayland - Logging Setup

Logging configuration and setup functionality.
"""

import logging
import logging.handlers
import sys
import typing

_logger = logging.getLogger(__name__)


class LoggingSetup:
    """Handles logging configuration and setup."""

    def __init__(self) -> None:
        """Initialize logging setup."""
        pass

    def setup_logging(self, log_level_str: str, log_file: typing.Optional[str] = None) -> None:
        """Set up logging configuration for the application.

        Args:
            log_level_str: Logging level string
            log_file: Optional path to log file for file logging
        """
        # Convert string level to logging level
        log_level = getattr(logging, log_level_str.upper(), logging.INFO)

        # Create root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Clear any existing handlers
        root_logger.handlers.clear()

        # Create formatters
        detailed_formatter = logging.Formatter(
            fmt="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        simple_formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(message)s",
            datefmt="%H:%M:%S",
        )

        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)

        # Use detailed format for DEBUG, simple for others
        if log_level == logging.DEBUG:
            console_handler.setFormatter(detailed_formatter)
        else:
            console_handler.setFormatter(simple_formatter)

        root_logger.addHandler(console_handler)

        # File handler if log file is specified
        if log_file:
            try:
                file_handler = logging.handlers.RotatingFileHandler(
                    log_file,
                    maxBytes=10 * 1024 * 1024,  # 10MB
                    backupCount=5,
                )
                file_handler.setLevel(logging.DEBUG)  # Always debug level for file
                file_handler.setFormatter(detailed_formatter)
                root_logger.addHandler(file_handler)

                logging.info(f"File logging enabled: {log_file}")
            except Exception as e:
                logging.error(f"Failed to setup file logging: {e}")

        # Set specific logger levels
        self._configure_third_party_loggers()

        logging.info(f"Logging configured with level: {log_level_str}")
        logging.debug("Debug logging is enabled")

    def _configure_third_party_loggers(self) -> None:
        """Configure logging levels for third-party libraries."""
        # Reduce verbosity of third-party libraries
        third_party_loggers = {
            "urllib3": logging.WARNING,
            "requests": logging.WARNING,
            "openai": logging.INFO,
            "httpx": logging.WARNING,
            "httpcore": logging.WARNING,
        }

        for logger_name, level in third_party_loggers.items():
            logger = logging.getLogger(logger_name)
            logger.setLevel(level)

    def get_logger(self, name: str) -> logging.Logger:
        """Get a logger instance with the given name.

        Args:
            name: Logger name (typically __name__)

        Returns:
            Logger instance
        """
        return logging.getLogger(name)

    @staticmethod
    def new() -> "LoggingSetup":
        """Create logging setup instance.

        Returns:
            LoggingSetup instance
        """
        return LoggingSetup()
