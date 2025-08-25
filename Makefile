# Whisper Wayland - Voice-to-Text Service Makefile

.PHONY: help install format lint typecheck test test-unit test-integration coverage clean all

# Default target
help:
	@echo "Whisper Wayland Development Commands"
	@echo "=================================="
	@echo ""
	@echo "Setup:"
	@echo "  install     Install dependencies with uv"
	@echo ""
	@echo "Code Quality:"
	@echo "  format      Format code with ruff"
	@echo "  lint        Lint code with ruff (PEP8 compliance)"
	@echo "  typecheck   Run type checking with mypy"
	@echo "  check       Run format, lint, and typecheck together"
	@echo ""
	@echo "Testing:"
	@echo "  test        Run all tests (depends on code quality checks)"
	@echo "  test-unit   Run only unit tests"
	@echo "  test-integration  Run only integration tests (requires OPENAI_API_KEY)"
	@echo "  coverage    Run tests with coverage report"
	@echo ""
	@echo "Utilities:"
	@echo "  clean       Clean up generated files"
	@echo "  all         Run complete pipeline (install, check, test)"
	@echo ""
	@echo "Environment:"
	@echo "  Set OPENAI_API_KEY environment variable for API tests"
	@echo "  Or create .env file with OPENAI_API_KEY=your_key_here"

# Install dependencies
install:
	@echo "Installing dependencies with uv..."
	uv sync

# Format code with ruff
format:
	@echo "Formatting code with ruff..."
	uv run ruff format .
	@echo "✅ Code formatting complete"

# Lint code with ruff (PEP8 compliance)
lint:
	@echo "Linting code with ruff..."
	uv run ruff check . --fix
	@echo "✅ Linting complete"

# Type checking with mypy
typecheck:
	@echo "Running type checks with mypy..."
	uv run mypy whisper_wayland/
	@echo "✅ Type checking complete"

# Run all code quality checks
check: format lint typecheck
	@echo "✅ All code quality checks passed"

# Run all tests
test: test-unit test-integration
	@echo "Running all tests..."
	uv run pytest --cov=whisper_wayland --cov-report=term --cov-report=html --cov-fail-under=50 -v
	@echo "✅ All tests passed with required coverage"

# Run only unit tests
test-unit:
	@echo "Running unit tests..."
	uv run pytest tests/unit --cov=whisper_wayland --cov-report=term --cov-report=html --cov-fail-under=50 -v

# Run only integration tests
test-integration:
	@echo "Running integration tests..."
	uv run pytest tests/integration -v

# Run tests with detailed coverage
coverage: check
	@echo "Running tests with detailed coverage..."
	uv run pytest --cov=whisper_wayland --cov-report=html --cov-report=term-missing --cov-fail-under=50
	@echo "📊 Coverage report generated in htmlcov/"

# Clean up generated files
clean:
	@echo "Cleaning up generated files..."
	rm -rf __pycache__ .pytest_cache .mypy_cache htmlcov
	rm -rf whisper_wayland/__pycache__ tests/__pycache__
	rm -rf tests/unit/__pycache__ tests/integration/__pycache__
	rm -f .coverage transcription.txt
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	@echo "✅ Cleanup complete"

# Complete pipeline
all: install check test
	@echo "🎉 Complete pipeline successful!"