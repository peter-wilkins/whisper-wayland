# Claude Development Context

This file contains development context and guidelines for AI assistants working on the Whisper Wayland project.

> **For users**: See [README.md][readme-md] for installation instructions, usage guide, and user documentation.

## Project Architecture

**Whisper Wayland** is a push-to-talk voice transcription service built with Python and designed for Wayland environments. The architecture follows a modular design with clear separation of concerns and clean API boundaries.

### Core Components

The service consists of seven main components that work together:

1. **Application** (`whisper_wayland/application.py`)
   - Main application orchestration and lifecycle management
   - Real-time global hotkey detection with push-to-talk functionality
   - Coordinates all service components with proper error handling
   - Manages hotkey callbacks and audio session processing

2. **Audio Recorder** (`whisper_wayland/audio_recorder.py`)
   - PyAudio integration for cross-platform audio capture
   - Configurable sample rate, chunk size, recording duration
   - Buffer management and WAV format conversion
   - Device selection and audio format validation

3. **Key Monitor** (`whisper_wayland/key_monitor.py`)
   - Global hotkey detection using evdev for Wayland/X11
   - Configurable key combinations and modifier support
   - Thread-safe event handling with press/release callbacks
   - Device discovery and permission handling

4. **Transcription Client** (`whisper_wayland/transcription_client.py`)
   - OpenAI Whisper API integration with retry logic
   - Error handling for network/API failures and rate limiting
   - Model selection and audio format validation
   - Connection testing and authentication validation

5. **Text Inserter** (`whisper_wayland/text_inserter.py`)
   - Cross-platform text insertion using multiple methods
   - Supports wtype, ydotool, xdotool, and clipboard fallback
   - Automatic method detection and preference handling
   - Text cleaning and insertion delay support

6. **Configuration** (`whisper_wayland/config.py`)
   - Environment variable management with comprehensive validation
   - `.env` file loading with fallback locations
   - Type-safe property access with descriptive error messages
   - Centralized configuration with masked logging for security

7. **Constants** (`whisper_wayland/constants.py`)
   - Static Constants class containing all application constants
   - Organized categories: audio, text processing, system limits, testing
   - Centralized constant management accessible via `ww.Constants`
   - Type-safe constant access throughout the codebase

## Repository Structure

```
whisper-wayland/
├── whisper_wayland/           # Main package
│   ├── __init__.py           # Package initialization & clean API exports
│   ├── main.py               # CLI entry point
│   ├── application.py        # Main application orchestration
│   ├── config.py             # Configuration management
│   ├── constants.py          # Application constants (Constants class)
│   ├── service_manager.py    # Service lifecycle management
│   ├── audio_recorder.py     # Audio capture component
│   ├── key_monitor.py        # Global hotkey detection
│   ├── transcription_client.py # OpenAI Whisper API integration
│   ├── text_inserter.py      # Cross-platform text insertion
│   └── logging_config.py     # Centralized logging configuration
├── tests/                     # Comprehensive test suite
│   ├── conftest.py           # Shared test configuration
│   ├── unit/                 # Unit tests (isolated components)
│   │   ├── conftest.py       # Unit test configuration
│   │   ├── test_config.py    # Configuration tests
│   │   ├── test_audio_recorder.py
│   │   ├── test_key_monitor.py
│   │   ├── test_transcription_client.py
│   │   ├── test_text_inserter.py
│   │   ├── test_service_manager.py
│   │   ├── test_main.py      # CLI and application tests
│   │   └── test_logging_config.py
│   └── integration/          # Integration tests (full workflows)
│       └── test_real_api.py  # Real OpenAI API integration tests
├── htmlcov/                  # Coverage reports (generated)
├── pyproject.toml           # uv configuration and dependencies
├── uv.lock                  # Dependency lock file
├── Makefile                 # Development automation
├── README.md                # User documentation
├── CLAUDE.md               # This development context file
└── WARP.md                 # Additional project documentation
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
make all               # Install deps, run all checks, and run tests

# Quality check workflows
make check             # Run all quality checks (format-check, lint-check, type-check)
make check-fix         # Run and fix all quality checks (format-fix, lint-fix, type-check)

# Individual development steps
make install           # Install all dependencies with uv
make format-fix        # Format code with ruff
make format-check      # Check code formatting (CI-friendly)
make lint-fix          # Lint and fix issues with ruff
make lint-check        # Check linting without fixes (CI-friendly)
make type-check        # Run mypy type checking

# Testing workflows
make tests             # Run all tests (unit + integration) with coverage
make tests-unit        # Run only unit tests with coverage
make tests-integration # Run only integration tests (requires OPENAI_API_KEY)
make coverage          # Run tests with detailed coverage report

# Utility commands
make clean             # Clean up generated files (.pyc, __pycache__, htmlcov, etc.)
make help              # Show all available commands with descriptions
```

**Manual commands** (when Makefile is not available):
```bash
# Run the service
uv run whisper-wayland

# Development quality checks
uv run ruff format .                    # Format code
uv run ruff check . --fix               # Lint and fix issues
uv run mypy .                           # Type checking (note: uses . not whisper_wayland/)

# Testing
uv run pytest --cov=whisper_wayland --cov-report=html --cov-report=term-missing --cov-fail-under=50
uv run pytest tests/unit -v             # Unit tests only
uv run pytest tests/integration -v      # Integration tests only (requires API key)
```

## Code Style and Standards

### Language Guidelines

- **Python Version**: Use Python 3.11+ features appropriately (tested on 3.11, 3.12, 3.13)
- **Type Hints**: Required throughout codebase (enforced by strict mypy configuration)
- **Code Organization**: Clean class-based design with static factory methods
- **Naming**: Use descriptive names following PEP 8 conventions
- **Documentation**: Comprehensive docstrings for all public APIs and components
- **Import Style**: 
  - **Package Imports**: Use `import whisper_wayland as ww` for internal imports
  - **Constants**: Access via `ww.Constants.CONSTANT_NAME` (never direct imports)
  - **External Libraries**: Prefer `import library` over `from library import item`
  - **Standard Library**: Use full imports (`import typing`) over selective imports
- **API Design**: 
  - All classes exposed through clean package namespace in `__init__.py`
  - Static factory methods (`.new()`) for component creation
  - Consistent error handling with specific exception types

### Code Quality Standards

- **Formatting**: Automated with ruff (PEP 8 compliant)
- **Import Sorting**: Handled by ruff (isort rules)
- **Line Length**: 88 characters (ruff default)
- **Type Checking**: Strict mypy configuration with no ignored errors
- **Security**: Bandit scanning for common vulnerabilities

### Architecture Principles

- **Separation of Concerns**: Each component has a single, well-defined responsibility
- **Clean API Design**: All classes exposed through package namespace with consistent interfaces
- **Dependency Injection**: Components receive dependencies rather than creating them
- **Error Boundaries**: Comprehensive error handling with specific exception types
- **Logging Strategy**: Centralized logging configuration with structured output
- **Thread Safety**: Proper synchronization for multi-threaded components (key monitoring, audio recording)
- **Configuration Management**: Type-safe environment variable handling with validation
- **Constant Organization**: All constants centralized in static `Constants` class

## Recent Architectural Improvements

The codebase has undergone significant architectural improvements to enhance maintainability and developer experience:

### Package Organization (Recent Changes)
- **Clean API Exports**: All classes exposed through `whisper_wayland` namespace
- **Constants Encapsulation**: All constants wrapped in static `Constants` class
- **Consistent Import Pattern**: Standardized `import whisper_wayland as ww` usage
- **Static Factory Methods**: All components use `.new()` class methods for creation
- **Separated Concerns**: Application logic separated from CLI entry point

### Import and Access Patterns
```python
# ✅ Correct import pattern
import whisper_wayland as ww

# ✅ Correct constant access
sample_rate = ww.Constants.DEFAULT_SAMPLE_RATE

# ✅ Correct component creation
config = ww.Config.get()
recorder = ww.AudioRecorder.new(config)
client = ww.TranscriptionClient.new(config)

# ❌ Avoid direct imports
from whisper_wayland.constants import DEFAULT_SAMPLE_RATE  # Don't do this
```

### Component Integration
- **Unified Error Handling**: All components have specific exception types
- **Configuration Validation**: Comprehensive type checking and validation
- **Logging Integration**: Centralized logging setup with proper formatting
- **Testing Infrastructure**: Complete unit and integration test coverage

## Development Guidelines

### Code Quality Requirements
- **100% Type Coverage**: All functions and methods must have proper type hints
- **Documentation**: All public APIs require comprehensive docstrings
- **Testing**: New features require both unit and integration tests
- **Error Handling**: All error conditions must be properly handled and logged

### Making Changes
1. **Follow Import Patterns**: Always use `import whisper_wayland as ww`
2. **Use Constants Class**: Access constants via `ww.Constants.CONSTANT_NAME`
3. **Add Type Hints**: All new code must include proper type annotations
4. **Write Tests**: Both unit and integration tests for new functionality
5. **Update Documentation**: Keep CLAUDE.md and README.md synchronized

### Testing Requirements
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: Test full workflows (require `OPENAI_API_KEY`)
- **Coverage**: Maintain minimum 50% test coverage
- **Quality Checks**: All changes must pass `make check` before commit

## Environment Setup

### Required Environment Variables
- `OPENAI_API_KEY`: Your OpenAI API key for Whisper transcription service
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `AUDIO_SAMPLE_RATE`: Audio recording sample rate (default: 16000)
- `AUDIO_CHUNK_SIZE`: Audio buffer chunk size (default: 1024)
- `MAX_RECORDING_DURATION`: Maximum recording duration in seconds (default: 30)
- `TEXT_INSERTION_DELAY`: Delay before text insertion (default: 0.1)
- `TEXT_INSERTION_METHOD`: Preferred text insertion method (wtype, ydotool, xdotool, clipboard)
- `HOTKEY`: Push-to-talk key combination (default: ctrl+compose)

### Environment File Setup
Create `.env` file in project root:
```bash
OPENAI_API_KEY=your_openai_api_key_here
LOG_LEVEL=INFO
HOTKEY=ctrl+compose
```

## Quick Start for Development

1. **Clone and Setup**:
   ```bash
   git clone <repository>
   cd whisper-wayland
   make install
   ```

2. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your OpenAI API key
   ```

3. **Run Quality Checks**:
   ```bash
   make check-fix    # Format, lint, and type-check
   ```

4. **Run Tests**:
   ```bash
   make tests-unit           # Unit tests only
   make tests-integration    # Integration tests (needs API key)
   make tests               # All tests
   ```

5. **Run Application**:
   ```bash
   uv run whisper-wayland
   ```

## Links and References

[readme-md]: README.md
[uv-docs]: https://docs.astral.sh/uv/