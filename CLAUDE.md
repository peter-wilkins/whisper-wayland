# Claude Development Contexts

This file contains development context and guidelines for AI assistants working on the Whisper Wayland project.

> **For users**: See [README.md][readme-md] for installation instructions, usage guide, and user documentation.

[Existing content remains unchanged]

## Testing Philosophy

### Test Principles
- Unit tests should be mocked and should have no external dependencies. 
- Integration tests are end-to-end tests. They should not use mocks. They should use the external dependencies (databases and services).
- Test mocks should be implemented in tests/unit/conftest.py and should be reused between tests as much as possible.

[Rest of the existing content remains unchanged]