# Whisper Claude - Voice-to-Text Service

[![CI](https://github.com/whisper-claude/whisper-claude/actions/workflows/ci.yml/badge.svg)](https://github.com/whisper-claude/whisper-claude/actions/workflows/ci.yml)

A push-to-talk voice transcription service that converts speech to text and inserts it at the cursor position in any application. Built for Ubuntu/Wayland without requiring root access.

## Features

- **Push-to-Talk**: Hold Compose key to record, release to transcribe and insert
- **Universal Text Insertion**: Works with any application that accepts text input
- **Wayland Support**: Native support for Wayland without root privileges
- **OpenAI Whisper Integration**: Uses OpenAI's Whisper API for accurate transcription
- **Docker Support**: Can run as a containerized service or system daemon
- **Comprehensive Error Handling**: Robust error handling with detailed logging
- **High Test Coverage**: 80%+ code coverage with real API integration tests

## Requirements

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install portaudio19-dev python3-dev wtype

# Fedora/RHEL
sudo dnf install portaudio-devel python3-devel wtype
```

### Python Dependencies

This project uses [uv](https://github.com/astral-sh/uv) for dependency management.

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync
```

## Configuration

All configuration is handled through environment variables:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for Whisper service | - | Yes |
| `WHISPER_MODEL` | Whisper model to use (tiny, base, small, medium, large) | `base` | No |
| `AUDIO_SAMPLE_RATE` | Audio recording sample rate | `16000` | No |
| `AUDIO_CHUNK_SIZE` | Audio buffer chunk size | `1024` | No |
| `MAX_RECORDING_DURATION` | Maximum recording duration in seconds | `30` | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `HOTKEY` | Push-to-talk key combination | `compose` | No |

## Installation & Usage

### Native Installation

1. **Set up environment**:
   ```bash
   # Option 1: Copy environment template
   cp .env.example .env
   # Edit with your OpenAI API key
   nano .env
   
   # Option 2: API key in separate file (already configured)
   # If you have .openai-api.key file, it will be automatically loaded
   ```

2. **Install and run**:
   ```bash
   # Install dependencies
   uv sync
   
   # Run the service
   uv run whisper-claude
   ```

### Docker Installation

1. **Build the image**:
   ```bash
   docker build -t whisper-claude .
   ```

2. **Run with audio and display access**:
   ```bash
   docker run -d \
     --name whisper-claude \
     --device /dev/snd \
     -e DISPLAY=$DISPLAY \
     -e WAYLAND_DISPLAY=$WAYLAND_DISPLAY \
     -e XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR \
     -v /tmp/.X11-unix:/tmp/.X11-unix \
     -v $XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR \
     --env-file .env \
     whisper-claude
   ```

### System Service Installation

1. **Install as systemd service**:
   ```bash
   # Copy service file
   sudo cp whisper-claude.service /etc/systemd/system/
   
   # Update service file with your paths and user
   sudo nano /etc/systemd/system/whisper-claude.service
   
   # Enable and start service
   sudo systemctl daemon-reload
   sudo systemctl enable whisper-claude
   sudo systemctl start whisper-claude
   ```

## Usage

1. **Start the service** using one of the installation methods above
2. **Press and hold Compose key** in any application where you want to insert text
3. **Speak clearly** while holding the key combination
4. **Release the keys** - the transcribed text will be inserted at cursor position

## Development

### Running Tests

```bash
# Run all tests with coverage
uv run pytest --cov=whisper_claude --cov-report=html --cov-report=term

# Run only unit tests
uv run pytest tests/unit/

# Run integration tests (requires OPENAI_API_KEY)
uv run pytest tests/integration/
```

### Continuous Integration

The project uses GitHub Actions for automated testing and quality checks:

- **Tests**: Run on every push to trunk with Python 3.11, 3.12, and 3.13
- **Linting**: Automated code formatting and style checking with ruff
- **Type Checking**: Static type analysis with mypy
- **Security Scanning**: Vulnerability detection with bandit
- **Coverage Reports**: Automatic coverage reporting and artifact uploads

All CI workflows run in Ubuntu environments with proper system dependencies installed.

### Code Quality

The project uses a comprehensive quality pipeline with Makefile automation:

```bash
# Complete development workflow
make all          # Install deps, run quality checks, and test

# Individual steps
make install      # Install dependencies
make format       # Format code with ruff
make lint         # Lint code with ruff (PEP8 compliance)
make typecheck    # Run type checking with mypy
make check        # Run all quality checks together

# Testing
make test         # Run all tests (after quality checks)
make test-unit    # Run only unit tests
make coverage     # Run tests with detailed coverage report

# Utilities
make clean        # Clean up generated files
make help         # Show all available commands
```

**Manual commands** (if needed):
```bash
# Format and lint with ruff
uv run ruff format .
uv run ruff check . --fix

# Type checking with mypy
uv run mypy whisper_claude/
```

## Architecture

The service consists of several key components:

- **Audio Recorder**: Captures audio using PyAudio with configurable quality settings
- **Key Monitor**: Global hotkey detection using evdev (full Wayland/X11 compatibility)
- **Transcription Client**: OpenAI Whisper API integration with error handling
- **Text Inserter**: Cross-platform text insertion using wtype for Wayland
- **Service Manager**: Coordinates all components with comprehensive error handling

## Troubleshooting

### Common Issues

1. **Audio not recording**: Ensure your user is in the `audio` group
2. **Text not inserting**: Verify `wtype` is installed and accessible
3. **Hotkey not working**: Check if another application is using Compose key
4. **Docker audio issues**: Ensure proper device mounting and permissions

### Debug Logging

Enable debug logging by setting `LOG_LEVEL=DEBUG` in your environment.

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Ensure 80%+ code coverage
5. Submit a pull request

## Support

For issues and feature requests, please use the GitHub issue tracker.
