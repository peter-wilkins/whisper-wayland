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
- **Import Style**: 
  - Strongly prefer using 'import ... as ...' over 'from ... import ...'
  - For instance, prefer 'import typing' (and then 'typing.Any') over 'from typing import Any'
  - Enforce this throughout the code base

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

[Remaining content continues as in the original file...]