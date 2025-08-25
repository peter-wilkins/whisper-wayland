"""Unit tests for text inserter module."""

import os
import subprocess
from unittest.mock import Mock, patch

import pytest

from whisper_wayland.config import Config
from whisper_wayland.constants import EXPECTED_DEVICE_COUNT
from whisper_wayland.text_inserter import (
    TextInserter,
    TextInsertionMethod,
    create_text_inserter,
)


class TestTextInsertionMethod:
    """Test cases for TextInsertionMethod enum."""

    def test_enum_values(self):
        """Test that enum has correct values."""
        assert TextInsertionMethod.WTYPE.value == "wtype"
        assert TextInsertionMethod.YDOTOOL.value == "ydotool"
        assert TextInsertionMethod.XDOTOOL.value == "xdotool"
        assert TextInsertionMethod.CLIPBOARD.value == "clipboard"


class TestTextInserter:
    """Test cases for TextInserter class."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TEXT_INSERTION_METHOD": "ydotool",
                "TEXT_INSERTION_DELAY": "0.1",
            },
        ):
            return Config()

    @pytest.fixture
    def mock_shutil_which(self):
        """Mock shutil.which to control available tools."""
        with patch("whisper_wayland.text_inserter.shutil.which") as mock:
            # By default, make ydotool available
            mock.side_effect = lambda tool: tool == "ydotool"
            yield mock

    @pytest.fixture
    def text_inserter(self, config, mock_shutil_which):
        """Create text inserter with mocked dependencies."""
        return TextInserter(config)

    def test_initialization_with_available_method(self, config, mock_shutil_which):
        """Test successful initialization with available method."""
        inserter = TextInserter(config)

        assert inserter.config == config
        assert inserter._preferred_method == TextInsertionMethod.YDOTOOL
        assert inserter._available_methods[TextInsertionMethod.YDOTOOL] is True
        assert inserter._available_methods[TextInsertionMethod.CLIPBOARD] is True

    def test_initialization_no_methods_available(self, config):
        """Test initialization when no methods are available."""
        with patch("whisper_wayland.text_inserter.shutil.which", return_value=None):
            # Even with no tools, clipboard should be available
            inserter = TextInserter(config)
            assert inserter._preferred_method == TextInsertionMethod.CLIPBOARD

    def test_detect_available_methods_all_available(self, config):
        """Test detection when all methods are available."""
        with patch("whisper_wayland.text_inserter.shutil.which", return_value="/usr/bin/tool"):
            inserter = TextInserter(config)

            assert all(inserter._available_methods.values())
            # Config is set to use ydotool, so even with all available, should use configured method
            assert inserter._preferred_method == TextInsertionMethod.YDOTOOL

    def test_detect_available_methods_partial(self, config):
        """Test detection with only some methods available."""

        def mock_which(tool):
            return "/usr/bin/tool" if tool in ["ydotool", "xdotool"] else None

        with patch("whisper_wayland.text_inserter.shutil.which", side_effect=mock_which):
            inserter = TextInserter(config)

            assert inserter._available_methods[TextInsertionMethod.WTYPE] is False
            assert inserter._available_methods[TextInsertionMethod.YDOTOOL] is True
            assert inserter._available_methods[TextInsertionMethod.XDOTOOL] is True
            assert inserter._available_methods[TextInsertionMethod.CLIPBOARD] is True

    def test_preferred_method_configuration_respected(self, mock_shutil_which):
        """Test that configured method is used when available."""
        with patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test123", "TEXT_INSERTION_METHOD": "xdotool"},
        ):
            # Make both ydotool and xdotool available
            mock_shutil_which.side_effect = lambda tool: tool in ["ydotool", "xdotool"]

            config = Config()
            inserter = TextInserter(config)

            assert inserter._preferred_method == TextInsertionMethod.XDOTOOL

    def test_preferred_method_fallback_when_configured_unavailable(self):
        """Test fallback when configured method is unavailable."""
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "TEXT_INSERTION_METHOD": "nonexistent",  # Configure a method that doesn't exist
            },
        ):
            with patch("whisper_wayland.text_inserter.shutil.which") as mock_which:
                # Only make ydotool available
                mock_which.side_effect = lambda tool: tool == "ydotool"

                config = Config()
                inserter = TextInserter(config)

                # Should fallback to ydotool since nonexistent method is not available
                assert inserter._preferred_method == TextInsertionMethod.YDOTOOL

    def test_insert_text_success(self, text_inserter):
        """Test successful text insertion."""
        with patch.object(text_inserter, "_insert_with_method", return_value=True) as mock_insert:
            result = text_inserter.insert_text("Hello, World!")

            assert result is True
            mock_insert.assert_called_once_with(TextInsertionMethod.YDOTOOL, "Hello, World!")

    def test_insert_text_empty(self, text_inserter):
        """Test text insertion with empty string."""
        result = text_inserter.insert_text("")

        assert result is False

    def test_insert_text_none(self, text_inserter):
        """Test text insertion with None."""
        # Convert None to empty string for cleaning
        with patch.object(text_inserter, "_clean_text_for_insertion", return_value=""):
            result = text_inserter.insert_text(None)

            assert result is False

    def test_insert_text_with_cleaning(self, text_inserter):
        """Test text insertion with text cleaning."""
        with patch.object(text_inserter, "_insert_with_method", return_value=True) as mock_insert:
            # Text with extra whitespace
            result = text_inserter.insert_text("  Hello,    World!  ")

            assert result is True
            # Should be cleaned to single spaces
            mock_insert.assert_called_once_with(TextInsertionMethod.YDOTOOL, "Hello, World!")

    def test_insert_text_with_delay(self, config, mock_shutil_which):
        """Test text insertion respects configured delay."""
        with patch.dict(os.environ, {"TEXT_INSERTION_DELAY": "0.5"}):
            config = Config()
            inserter = TextInserter(config)

            with patch("time.sleep") as mock_sleep, patch.object(
                inserter, "_insert_with_method", return_value=True
            ):
                inserter.insert_text("test")

                mock_sleep.assert_called_once_with(0.5)

    def test_insert_text_fallback_on_failure(self, text_inserter):
        """Test fallback methods when primary method fails."""
        with patch.object(text_inserter, "_insert_with_method") as mock_insert, patch.object(
            text_inserter, "_try_fallback_methods", return_value=True
        ) as mock_fallback:
            # Primary method fails
            mock_insert.return_value = False

            result = text_inserter.insert_text("test")

            assert result is True
            mock_fallback.assert_called_once_with("test")

    def test_insert_text_all_methods_fail(self, text_inserter):
        """Test when all insertion methods fail."""
        with patch.object(text_inserter, "_insert_with_method", return_value=False), patch.object(
            text_inserter, "_try_fallback_methods", return_value=False
        ):
            result = text_inserter.insert_text("test")

            assert result is False

    def test_clean_text_for_insertion_basic(self, text_inserter):
        """Test basic text cleaning."""
        # Test strip whitespace
        assert text_inserter._clean_text_for_insertion("  hello  ") == "hello"

        # Test multiple spaces
        assert text_inserter._clean_text_for_insertion("hello    world") == "hello world"

        # Test combined
        assert text_inserter._clean_text_for_insertion("  hello    world  ") == "hello world"

    def test_clean_text_for_insertion_edge_cases(self, text_inserter):
        """Test text cleaning edge cases."""
        # Empty string
        assert text_inserter._clean_text_for_insertion("") == ""

        # Only whitespace
        assert text_inserter._clean_text_for_insertion("   ") == ""

        # Already clean
        assert text_inserter._clean_text_for_insertion("hello world") == "hello world"

    def test_insert_with_wtype(self, text_inserter):
        """Test wtype insertion method."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = text_inserter._insert_with_wtype("test text")

            assert result is True
            mock_run.assert_called_once_with(
                ["wtype", "test text"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

    def test_insert_with_ydotool(self, text_inserter):
        """Test ydotool insertion method."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = text_inserter._insert_with_ydotool("test text")

            assert result is True
            mock_run.assert_called_once_with(
                ["ydotool", "type", "test text"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

    def test_insert_with_xdotool(self, text_inserter):
        """Test xdotool insertion method."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            result = text_inserter._insert_with_xdotool("test text")

            assert result is True
            mock_run.assert_called_once_with(
                ["xdotool", "type", "--delay", "10", "test text"],
                check=False,
                capture_output=True,
                text=True,
                timeout=10,
            )

    def test_insert_with_clipboard_wl_copy(self, text_inserter):
        """Test clipboard insertion with wl-copy."""
        mock_result = Mock()
        mock_result.returncode = 0

        # Mock ydotool available for paste command
        text_inserter._available_methods[TextInsertionMethod.YDOTOOL] = True

        def mock_which(tool):
            return "/usr/bin/tool" if tool == "wl-copy" else None

        with patch("subprocess.run", return_value=mock_result) as mock_run, patch(
            "whisper_wayland.text_inserter.shutil.which", side_effect=mock_which
        ):
            result = text_inserter._insert_with_clipboard("test text")

            assert result is True
            assert mock_run.call_count == EXPECTED_DEVICE_COUNT  # wl-copy + ydotool paste

    def test_insert_with_clipboard_xclip(self, text_inserter):
        """Test clipboard insertion with xclip."""
        mock_result = Mock()
        mock_result.returncode = 0

        # Mock xdotool available for paste command
        text_inserter._available_methods[TextInsertionMethod.XDOTOOL] = True

        def mock_which(tool):
            if tool == "wl-copy":
                return None  # Not available
            elif tool == "xclip":
                return "/usr/bin/xclip"
            return None

        with patch("subprocess.run", return_value=mock_result) as mock_run, patch(
            "whisper_wayland.text_inserter.shutil.which", side_effect=mock_which
        ):
            result = text_inserter._insert_with_clipboard("test text")

            assert result is True
            assert mock_run.call_count == EXPECTED_DEVICE_COUNT  # xclip + xdotool paste

    def test_insert_method_failure(self, text_inserter):
        """Test handling of subprocess failures."""
        # Mock subprocess.run directly to avoid actually calling it
        mock_result = Mock()
        mock_result.returncode = 1  # Non-zero return code indicates failure

        with patch("subprocess.run", return_value=mock_result):
            result = text_inserter._insert_with_ydotool("test")

            assert result is False

    def test_insert_method_timeout(self, text_inserter):
        """Test handling of subprocess timeouts."""
        # Test through the wrapper method that has exception handling
        with patch("subprocess.run") as mock_run:
            # Configure the mock to raise TimeoutExpired
            mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)

            result = text_inserter._insert_with_method(TextInsertionMethod.YDOTOOL, "test")

            assert result is False

    def test_try_fallback_methods_success(self, text_inserter):
        """Test successful fallback method."""
        # Make multiple methods available
        text_inserter._available_methods.update(
            {
                TextInsertionMethod.WTYPE: True,
                TextInsertionMethod.XDOTOOL: True,
            }
        )

        with patch.object(text_inserter, "_insert_with_method") as mock_insert:
            # First fallback (YDOTOOL) fails, second (WTYPE) succeeds
            mock_insert.side_effect = [False, True]

            result = text_inserter._try_fallback_methods("test")

            assert result is True
            assert mock_insert.call_count == EXPECTED_DEVICE_COUNT

    def test_try_fallback_methods_all_fail(self, text_inserter):
        """Test when all fallback methods fail."""
        # Make multiple methods available
        text_inserter._available_methods.update(
            {
                TextInsertionMethod.WTYPE: True,
                TextInsertionMethod.XDOTOOL: True,
            }
        )

        with patch.object(text_inserter, "_insert_with_method", return_value=False):
            result = text_inserter._try_fallback_methods("test")

            assert result is False

    def test_test_insertion_wtype(self, config, mock_shutil_which):
        """Test insertion capability test for wtype."""
        mock_shutil_which.side_effect = lambda tool: tool == "wtype"

        inserter = TextInserter(config)
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = inserter.test_insertion()

            assert result is True

    def test_test_insertion_ydotool(self, text_inserter):
        """Test insertion capability test for ydotool."""
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = text_inserter.test_insertion()

            assert result is True

    def test_test_insertion_xdotool(self, config, mock_shutil_which):
        """Test insertion capability test for xdotool."""
        mock_shutil_which.side_effect = lambda tool: tool == "xdotool"

        inserter = TextInserter(config)
        mock_result = Mock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = inserter.test_insertion()

            assert result is True

    def test_test_insertion_clipboard(self, config):
        """Test insertion capability test for clipboard."""
        with patch("whisper_wayland.text_inserter.shutil.which") as mock_which:
            # No direct tools available, should fallback to clipboard
            mock_which.side_effect = (
                lambda tool: tool == "wl-copy" if tool in ["wl-copy", "xclip"] else None
            )

            inserter = TextInserter(config)
            result = inserter.test_insertion()

            assert result is True

    def test_test_insertion_failure(self, text_inserter):
        """Test insertion capability test failure."""
        with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")):
            result = text_inserter.test_insertion()

            assert result is False

    def test_get_available_methods(self, text_inserter):
        """Test getting available methods."""
        # Set up known available methods
        text_inserter._available_methods = {
            TextInsertionMethod.YDOTOOL: True,
            TextInsertionMethod.CLIPBOARD: True,
            TextInsertionMethod.WTYPE: False,
            TextInsertionMethod.XDOTOOL: False,
        }

        methods = text_inserter.get_available_methods()

        assert set(methods) == {"ydotool", "clipboard"}

    def test_get_preferred_method(self, text_inserter):
        """Test getting preferred method."""
        method = text_inserter.get_preferred_method()

        assert method == "ydotool"

    def test_get_preferred_method_none(self, config):
        """Test getting preferred method when none available."""
        with patch("whisper_wayland.text_inserter.shutil.which", return_value=None):
            # This should still have clipboard as fallback
            inserter = TextInserter(config)
            method = inserter.get_preferred_method()

            assert method == "clipboard"

    def test_close(self, text_inserter):
        """Test text inserter cleanup."""
        # Should not raise any errors
        text_inserter.close()


class TestCreateTextInserter:
    """Test cases for create_text_inserter factory function."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            return Config()

    def test_create_text_inserter_success(self, config):
        """Test successful text inserter creation."""
        with patch("whisper_wayland.text_inserter.shutil.which", return_value="/usr/bin/tool"):
            inserter = create_text_inserter(config)

            assert isinstance(inserter, TextInserter)
            assert inserter.config == config

    def test_create_text_inserter_no_methods_available(self, config):
        """Test creation when no methods are available."""
        with patch("whisper_wayland.text_inserter.shutil.which") as mock_which:
            # Make only clipboard tools unavailable to force error
            mock_which.return_value = None

            # Even with no tools, clipboard should be available as fallback
            inserter = create_text_inserter(config)
            assert isinstance(inserter, TextInserter)
