"""Whisper Wayland - Main Entry Point

A push-to-talk voice transcription service that converts speech to text
and inserts it at the cursor position in any application.
"""

import os
import sys

import whisper_wayland as ww
import whisper_wayland.config as config


def main() -> None:
    """Main entry point for the application."""
    try:
        # Check for config file argument
        config_file = None
        if len(sys.argv) > 1:
            config_file = sys.argv[1]
            if not os.path.exists(config_file):
                print(f"Error: Configuration file '{config_file}' not found")
                sys.exit(1)

        # Create and run application
        app = ww.Application(config_file)
        app.run()
        sys.exit(0)

    except config.ConfigError as e:
        print(f"Configuration error: {e}")
        print("Please check your environment variables or .env file")
        sys.exit(1)
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
