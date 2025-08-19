# Claude Development Context

This file contains important context for Claude when working on this project.

## Project Overview

**Whisper Wayland** is a push-to-talk voice transcription service that converts speech to text and inserts it at the cursor position in any application. Built specifically for Ubuntu/Wayland environments without requiring root access.

## Key Requirements

### Functional Requirements
- **Push-to-talk hotkey**: Compose key to activate recording
- **Universal text insertion**: Works with any application that accepts text input
- **Wayland compatibility**: Must work on Wayland without root privileges
- **OpenAI Whisper integration**: Uses OpenAI API for transcription (tiny/base models initially)
- **English-only support**: No multi-language requirements
- **Deployment flexibility**: Can run natively, as Docker container, or systemd service

### Technical Requirements
- **Language**: Python with idiomatic code style
- **Dependency management**: uv package manager
- **Code organization**: Prefer functions over classes unless classes are necessary
- **Configuration**: Environment variables only
- **Error handling**: Extensive error handling throughout
- **Logging**: Comprehensive info logging and extensive debug logging
- **Testing**: 80%+ code coverage with minimal mocking (prefer real API calls)
- **Documentation**: Well-documented code

### System Dependencies
- **Audio**: PyAudio for recording (works with Wayland)
- **Key capture**: evdev for global hotkeys (full Wayland/X11 compatibility)
- **Text insertion**: wtype for Wayland text insertion
- **Container support**: Docker-ready with proper audio/display access

## Architecture Components

The service is designed with these key components:

1. **Audio Recorder** (`audio_recorder.py`)
   - Uses PyAudio for cross-platform audio capture
   - Configurable sample rate, chunk size, recording duration
   - Buffer management and audio format handling

2. **Key Monitor** (`key_monitor.py`)
   - Global hotkey detection using evdev
   - Full Wayland/X11 compatibility (may require input group membership)
   - Configurable key combinations

3. **Transcription Client** (`transcription_client.py`)
   - OpenAI Whisper API integration
   - Error handling for network/API failures
   - Model selection (tiny, base, etc.)

4. **Text Inserter** (`text_inserter.py`)
   - Cross-platform text insertion
   - Uses wtype for Wayland compatibility
   - Handles various application contexts

5. **Service Manager** (`service_manager.py`)
   - Coordinates all components
   - Manages service lifecycle
   - Central error handling and logging

6. **Configuration** (`config.py`)
   - Environment variable management
   - Default value handling
   - Validation

## Environment Variables

| Variable | Purpose | Default | Notes |
|----------|---------|---------|-------|
| `OPENAI_API_KEY` | OpenAI API authentication | Required | For Whisper API access |
| `WHISPER_MODEL` | Whisper model selection | `base` | tiny, base, small, medium, large |
| `AUDIO_SAMPLE_RATE` | Recording sample rate | `16000` | Standard for speech |
| `AUDIO_CHUNK_SIZE` | Audio buffer size | `1024` | Performance tuning |
| `MAX_RECORDING_DURATION` | Max recording time | `30` | Seconds |
| `LOG_LEVEL` | Logging verbosity | `INFO` | DEBUG, INFO, WARNING, ERROR |
| `HOTKEY` | Push-to-talk combination | `compose` | Key binding |

## Development Guidelines

### Code Style
- Use type hints throughout
- Prefer composition over inheritance
- Keep functions focused and single-purpose
- Use descriptive variable and function names
- Follow PEP 8 style guidelines (enforced by ruff)
- Code formatting handled by ruff formatter
- Import sorting handled by ruff (isort rules)

### Error Handling
- Catch specific exceptions rather than broad except clauses
- Provide meaningful error messages
- Log errors with appropriate context
- Graceful degradation when possible
- User-friendly error reporting

### Logging Strategy
- **DEBUG**: Detailed execution flow, variable values, API calls
- **INFO**: Service lifecycle, successful operations, user actions
- **WARNING**: Recoverable errors, fallback usage
- **ERROR**: Failed operations, exceptions

### Testing Strategy
- **Unit tests**: Individual component testing with minimal mocking
- **Integration tests**: Full workflow testing with real OpenAI API
- **Coverage target**: 80% minimum
- **Test structure**: Separate unit and integration test directories
- **API testing**: Use real OpenAI API key for authentic testing

### Docker Considerations
- **Audio access**: Requires /dev/snd device mounting
- **Display access**: Wayland/X11 socket mounting for text insertion
- **User permissions**: Run as non-root user
- **Environment**: Support both environment files and variables

### Service Installation
- **Native**: Direct Python execution with uv
- **systemd**: User service (no root required)
- **Docker**: Containerized with proper device access

## Development Workflow

### Commit Strategy
- When we execute a plan, let's make sure we commit as often as it makes sense
- The commits should be small and reasonable
- Always use meaningful commit messages

## File Structure

```
whisper-wayland/
├── whisper_wayland/
│   ├── __init__.py
│   ├── main.py                 # Entry point
│   ├── config.py              # Environment variable handling
│   ├── service_manager.py     # Main service coordination
│   ├── audio_recorder.py      # PyAudio recording
│   ├── key_monitor.py         # pynput hotkey detection
│   ├── transcription_client.py # OpenAI Whisper API
│   └── text_inserter.py       # wtype text insertion
├── tests/
│   ├── unit/                  # Unit tests
│   └── integration/           # Integration tests
├── docker/
│   └── Dockerfile
├── systemd/
│   └── whisper-wayland.service
├── pyproject.toml             # uv configuration
├── .env.example               # Environment template
├── README.md                  # User documentation
└── CLAUDE.md                  # This file
```

## Common Commands

### Development

**Recommended workflow using Makefile:**
```bash
# Complete development pipeline
make all          # Install, check quality, run tests

# Individual steps
make install      # Install dependencies
make check        # Run formatter, linter, type checker
make test         # Run all tests with coverage
make coverage     # Detailed coverage report

# Manual commands (if needed)
uv run whisper-wayland                    # Run service
uv run ruff format . && uv run ruff check . --fix  # Format & lint
uv run mypy whisper_wayland/              # Type checking
```

**API Key Setup:**
- The OpenAI API key should be in `.openai-api.key` file
- Alternatively, set `OPENAI_API_KEY` environment variable
- Or create `.env` file with the key

### Docker
```bash
# Build image
docker build -t whisper-wayland .

# Run with audio/display access
docker run -d --name whisper-wayland --device /dev/snd -e DISPLAY=$DISPLAY -e WAYLAND_DISPLAY=$WAYLAND_DISPLAY -e XDG_RUNTIME_DIR=$XDG_RUNTIME_DIR -v /tmp/.X11-unix:/tmp/.X11-unix -v $XDG_RUNTIME_DIR:$XDG_RUNTIME_DIR --env-file .env whisper-wayland
```

### Service Management
```bash
# Install systemd service
sudo cp whisper-wayland.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable whisper-wayland
sudo systemctl start whisper-wayland

# Check service status
systemctl status whisper-wayland

# View logs
journalctl -u whisper-wayland -f
```

## Troubleshooting Notes

### Audio Issues
- User must be in `audio` group
- PulseAudio/ALSA permissions
- Check available audio devices

### Wayland Compatibility
- Ensure wtype is installed and accessible
- XDG_RUNTIME_DIR properly set
- Wayland socket permissions

### API Integration
- Validate OpenAI API key format
- Handle rate limiting gracefully
- Network timeout handling
- Audio format compatibility with Whisper API

### Performance Considerations
- Audio buffer management
- Memory usage with long recordings
- CPU usage during transcription
- Network bandwidth for API calls

## Security Notes

- OpenAI API key must be securely stored
- No sensitive data logging
- Audio data should not be persisted unnecessarily
- Service runs with minimal privileges

## Development Practices

- All temporary files that should be created (for trouble-shooting, etc) should be created in /tmp (just to make sure we are not commiting these by accident)