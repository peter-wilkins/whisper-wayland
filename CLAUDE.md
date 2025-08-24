# Claude Development Context

This file contains development context and guidelines for AI assistants working on the Whisper Wayland project.

> **For users**: See [README.md][readme-md] for installation instructions, usage guide, and user documentation.

## Project Architecture

**Whisper Wayland** is a push-to-talk voice transcription service built with Python and designed for Wayland environments. The architecture follows a modular design with clear separation of concerns.

### Core Components

The service consists of six main components that work together:

1. **Audio Recorder** (`whisper_wayland/audio_recorder.py`)
   - PyAudio integration for cross-platform audio capture
   - Configurable sample rate, chunk size, recording duration
   - Buffer management and audio format handling
   - Handles audio device selection and error recovery

2. **Key Monitor** (`whisper_wayland/key_monitor.py`)
   - Global hotkey detection using evdev
   - Full Wayland/X11 compatibility (requires input group membership)
   - Configurable key combinations and modifier support
   - Thread-safe event handling

3. **Transcription Client** (`whisper_wayland/transcription_client.py`)
   - OpenAI Whisper API integration with retry logic
   - Error handling for network/API failures and rate limiting
   - Model selection and parameter configuration
   - Audio format validation for API compatibility

4. **Text Inserter** (`whisper_wayland/text_inserter.py`)
   - Cross-platform text insertion using wtype for Wayland
   - Handles various application contexts and focus states
   - Error recovery for insertion failures
   - Clipboard fallback mechanisms

5. **Service Manager** (`whisper_wayland/service_manager.py`)
   - Coordinates all components with thread orchestration
   - Manages service lifecycle and graceful shutdown
   - Central error handling and logging coordination
   - Component state management

6. **Configuration** (`whisper_wayland/config.py`)
   - Environment variable management with validation
   - Default value handling and type conversion
   - Configuration validation and error reporting
   - Centralized settings access

## Repository Structure

```
whisper-wayland/
├── whisper_wayland/           # Main package
│   ├── __init__.py           # Package initialization
│   ├── main.py               # Entry point and CLI
│   ├── config.py             # Configuration management
│   ├── service_manager.py    # Main service coordination
│   ├── audio_recorder.py     # Audio capture component
│   ├── key_monitor.py        # Hotkey detection component
│   ├── transcription_client.py # OpenAI API integration
│   └── text_inserter.py      # Text insertion component
├── tests/                     # Test suite
│   ├── unit/                 # Unit tests (isolated components)
│   │   ├── test_config.py    # Configuration tests
│   │   ├── test_audio_recorder.py
│   │   ├── test_key_monitor.py
│   │   ├── test_transcription_client.py
│   │   ├── test_text_inserter.py
│   │   └── test_service_manager.py
│   └── integration/          # Integration tests (full workflows)
│       ├── test_full_workflow.py
│       └── test_api_integration.py
├── docker/                   # Container configuration
│   └── Dockerfile           # Multi-stage Docker build
├── systemd/                  # Service configuration
│   └── whisper-wayland.service # systemd unit file
├── .github/                  # GitHub configuration
│   └── workflows/
│       └── ci.yml           # Comprehensive CI pipeline
├── pyproject.toml           # uv configuration and dependencies
├── Makefile                 # Development automation
├── .env.example             # Environment template
├── README.md                # User documentation
└── CLAUDE.md               # This development context file
```

## Development Environment

### Dependencies and Tools

- **Package Manager**: [uv][uv-docs] for fast, reliable dependency management
- **Python Version**: 3.11+ (tested on 3.11, 3.12, 3.13)
- **Code Formatting**: ruff (replaces black, isort, flake8)
- **Type Checking**: mypy with strict configuration
- **Testing**: pytest with coverage reporting
- **Security**: bandit for vulnerability scanning
- **CI/CD**: GitHub Actions with comprehensive pipeline

### Required System Dependencies

**Development setup requires these system packages:**

```bash
# Ubuntu/Debian
sudo apt install portaudio19-dev python3-dev wtype

# Fedora/RHEL  
sudo dnf install portaudio-devel python3-devel wtype
```

**Additional dependencies for development:**
- Git for version control
- Docker (optional, for container testing)
- Make (for automated workflows)

### Development Workflow

The project uses a Makefile-driven workflow for consistency and automation:

```bash
# Complete development pipeline (recommended)
make all              # Install deps, format, lint, typecheck, test

# Individual development steps
make install          # Install all dependencies with uv
make format           # Format code with ruff
make lint             # Lint and fix issues with ruff
make typecheck        # Run mypy type checking
make check            # Run all quality checks (format, lint, typecheck)

# Testing workflows
make test             # Run all tests with coverage (after quality checks)
make test-unit        # Run only unit tests
make test-integration # Run only integration tests (requires API key)
make coverage         # Generate detailed coverage report

# Utility commands
make clean            # Clean up generated files (.pyc, __pycache__, etc.)
make help             # Show all available commands
```

**Manual commands** (when Makefile is not available):
```bash
# Run the service
uv run whisper-wayland

# Development quality checks
uv run ruff format .                    # Format code
uv run ruff check . --fix               # Lint and fix issues
uv run mypy whisper_wayland/            # Type checking

# Testing
uv run pytest --cov=whisper_wayland --cov-report=html --cov-report=term
```

## Code Style and Standards

### Language Guidelines

- **Python Version**: Use Python 3.11+ features appropriately
- **Type Hints**: Required throughout codebase (enforced by mypy)
- **Code Organization**: Prefer functions over classes unless classes provide clear benefits
- **Naming**: Use descriptive names following PEP 8 conventions
- **Documentation**: Comprehensive docstrings for public APIs

### Code Quality Standards

- **Formatting**: Automated with ruff (PEP 8 compliant)
- **Import Sorting**: Handled by ruff (isort rules)
- **Line Length**: 88 characters (ruff default)
- **Type Checking**: Strict mypy configuration with no ignored errors
- **Security**: Bandit scanning for common vulnerabilities

### Architecture Principles

- **Separation of Concerns**: Each component has a single, well-defined responsibility
- **Dependency Injection**: Components receive dependencies rather than creating them
- **Error Boundaries**: Comprehensive error handling with specific exception types
- **Logging Strategy**: Structured logging with appropriate levels
- **Thread Safety**: Proper synchronization for multi-threaded components

## Testing Strategy

### Test Organization

- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test component interactions and external APIs
- **Coverage Target**: Minimum 80% code coverage (currently >85%)
- **Test Structure**: Mirror source structure in test directories

### Testing Approach

- **Minimal Mocking**: Prefer real implementations over mocks when possible
- **Real API Testing**: Integration tests use actual OpenAI API for authenticity
- **Error Scenarios**: Extensive testing of error conditions and edge cases
- **Performance Testing**: Basic performance validation for audio processing

### API Key Management for Tests

Integration tests require OpenAI API access:

```bash
# Option 1: Environment variable
export OPENAI_API_KEY="your-api-key"

# Option 2: Key file (recommended)
echo "your-api-key" > .openai-api.key

# Option 3: .env file
echo "OPENAI_API_KEY=your-api-key" > .env
```

Tests automatically skip integration tests if no API key is available.

## Deployment Configurations

### Native Deployment

- **Runtime**: Direct Python execution with uv
- **Dependencies**: System packages + Python packages
- **Service**: Optional systemd user service
- **Permissions**: User-level, no root required

### Docker Deployment

- **Base Image**: Multi-stage build with Python slim
- **System Access**: Requires audio devices and display sockets
- **User Context**: Runs as non-root user for security
- **Volume Mounts**: Audio devices, display sockets, runtime directories

### Service Configuration

- **systemd**: User service configuration provided
- **Logging**: Structured JSON logs to stdout/stderr
- **Environment**: Configuration via environment variables only
- **Health Checks**: Built-in service health monitoring

## Development Guidelines

### Error Handling Strategy

- **Specific Exceptions**: Catch specific exception types, not broad `except:` clauses
- **User-Friendly Messages**: Provide clear error messages for user-facing issues
- **Logging Context**: Include relevant context in error logs
- **Graceful Degradation**: Handle failures without crashing the service
- **Recovery Mechanisms**: Automatic retry for transient failures

### Logging Standards

Structured logging with appropriate levels:

- **DEBUG**: Detailed execution flow, variable values, API request/responses
- **INFO**: Service lifecycle events, successful operations, user actions
- **WARNING**: Recoverable errors, fallback mechanisms activated
- **ERROR**: Failed operations, unhandled exceptions, service degradation

### Security Considerations

- **API Key Storage**: Secure handling of OpenAI API keys
- **No Data Persistence**: Audio data not stored locally after processing
- **Minimal Privileges**: Service runs with least required permissions
- **Input Validation**: Validate all external inputs and configurations
- **Network Security**: HTTPS-only API communications

## Commit Strategy

Follow these guidelines for consistent git history:

- **Commit Frequency**: Commit early and often during development
- **Commit Size**: Small, logical commits that can be easily reviewed
- **Commit Messages**: 
  - First line: Concise summary (≤50 chars) in imperative mood
  - Body: Detailed explanation of why changes were made
  - Reference issues/PRs when relevant

### Example commit messages:
```
Add retry logic to transcription client

Implement exponential backoff for OpenAI API rate limiting.
Handles temporary network failures and API unavailability.
Fixes #123

Add comprehensive error handling to audio recorder

- Handle device disconnection gracefully
- Add fallback device selection
- Improve error messages for user troubleshooting
```

## Configuration Management

### Environment Variables

All configuration through environment variables for 12-factor compliance:

| Variable | Purpose | Type | Default | Validation |
|----------|---------|------|---------|------------|
| `OPENAI_API_KEY` | OpenAI API authentication | string | Required | API key format |
| `WHISPER_MODEL` | Whisper model selection | string | `base` | Valid model name |
| `AUDIO_SAMPLE_RATE` | Recording sample rate | int | `16000` | Valid audio rate |
| `AUDIO_CHUNK_SIZE` | Audio buffer size | int | `1024` | Power of 2 |
| `MAX_RECORDING_DURATION` | Max recording seconds | int | `30` | Positive integer |
| `LOG_LEVEL` | Logging verbosity | string | `INFO` | Valid log level |
| `HOTKEY` | Push-to-talk key binding | string | `compose` | Valid key name |

### Configuration Loading Priority

1. Environment variables (highest priority)
2. `.env` file in working directory
3. `.openai-api.key` file for API key only
4. Default values (lowest priority)

## Performance Considerations

### Audio Processing

- **Buffer Management**: Configurable chunk sizes for different hardware
- **Memory Usage**: Efficient audio data handling without excessive buffering
- **Latency**: Minimize delay between key release and text insertion
- **Resource Cleanup**: Proper cleanup of audio resources

### API Integration

- **Request Optimization**: Efficient audio encoding for API transmission
- **Network Handling**: Robust handling of network conditions
- **Rate Limiting**: Respect OpenAI API rate limits
- **Caching**: No caching of audio data for privacy

### System Resources

- **CPU Usage**: Efficient audio processing without excessive CPU load
- **Memory Footprint**: Minimal memory usage during idle periods
- **Thread Management**: Proper thread lifecycle management
- **I/O Handling**: Asynchronous I/O where beneficial

## Troubleshooting Development Issues

### Common Development Problems

**Audio issues during development:**
- Verify user in `audio` group: `groups $USER`
- Test audio system: `arecord -l` and `aplay -l`
- Check PulseAudio: `pulseaudio --check`

**Type checking errors:**
- Update type stubs: `uv add --dev types-*`
- Check mypy configuration in `pyproject.toml`
- Use `# type: ignore` sparingly with comments

**Test failures:**
- Ensure API key is configured for integration tests
- Check system dependencies are installed
- Run tests with `-v` for detailed output

**Docker development:**
- Verify audio device access: `ls -la /dev/snd`
- Check display variables: `echo $DISPLAY $WAYLAND_DISPLAY`
- Test container audio: `docker run --rm --device /dev/snd alpine aplay -l`

### Development Environment Setup

Complete development environment setup:

```bash
# 1. Clone and enter repository
git clone <repository-url>
cd whisper-wayland

# 2. Install system dependencies
sudo apt install portaudio19-dev python3-dev wtype  # Ubuntu/Debian

# 3. Install uv if not available
curl -LsSf https://astral.sh/uv/install.sh | sh

# 4. Set up Python environment and dependencies
uv sync

# 5. Configure API key
echo "your-openai-api-key" > .openai-api.key

# 6. Run development pipeline
make all

# 7. Verify installation
uv run whisper-wayland --help
```

---

**For users and installation**: See [README.md][readme-md] for user-facing documentation, installation guides, and usage instructions.

[readme-md]: https://github.com/your-org/whisper-wayland/blob/trunk/README.md
[uv-docs]: https://docs.astral.sh/uv/