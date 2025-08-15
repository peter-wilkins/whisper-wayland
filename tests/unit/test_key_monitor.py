"""Unit tests for key monitor module."""

import os
import time
from unittest.mock import Mock, patch

import pytest

from whisper_claude.config import Config
from whisper_claude.key_monitor import KeyMonitor, KeyMonitorError, create_key_monitor


class TestKeyMonitor:
    """Test cases for KeyMonitor class with real implementation."""

    @pytest.fixture
    def config(self, mock_api_key):
        """Create test configuration."""
        with patch.dict(os.environ, {"HOTKEY": "ctrl+alt+space"}):
            return Config()

    @pytest.fixture
    def mock_listener(self):
        """Create mock pynput listener."""
        with patch(
            "whisper_claude.key_monitor.keyboard.Listener"
        ) as mock_listener_class:
            mock_listener_instance = Mock()
            mock_listener_class.return_value = mock_listener_instance
            yield mock_listener_instance

    def test_key_monitor_initialization(self, config):
        """Test key monitor initialization with valid config."""
        monitor = KeyMonitor(config)

        assert monitor.config == config
        assert monitor._callback is None
        assert monitor._release_callback is None
        assert not monitor._monitoring
        assert not monitor._hotkey_pressed
        assert monitor._hotkey_combination == {"ctrl", "alt", "space"}

    def test_key_monitor_initialization_custom_hotkey(self, mock_api_key):
        """Test key monitor initialization with custom hotkey."""
        with patch.dict(os.environ, {"HOTKEY": "ctrl+shift+f1"}):
            config = Config()
            monitor = KeyMonitor(config)

            assert monitor._hotkey_combination == {"ctrl", "shift", "f1"}

    def test_key_monitor_initialization_invalid_hotkey(self, mock_api_key):
        """Test key monitor initialization with invalid hotkey."""
        with patch.dict(os.environ, {"HOTKEY": ""}):
            config = Config()
            with pytest.raises(KeyMonitorError, match="Hotkey cannot be empty"):
                KeyMonitor(config)

    def test_parse_hotkey_combination_various_formats(self, mock_api_key):
        """Test hotkey parsing with various input formats."""
        # Test different input formats
        test_cases = [
            ("ctrl+space", {"ctrl", "space"}),
            ("ctrl+alt+space", {"ctrl", "alt", "space"}),
            ("shift+a", {"shift", "a"}),
            ("ctrl+shift+enter", {"ctrl", "shift", "enter"}),
        ]

        for hotkey_str, expected in test_cases:
            with patch.dict(os.environ, {"HOTKEY": hotkey_str}):
                config = Config()
                monitor = KeyMonitor(config)
                assert monitor._hotkey_combination == expected

    def test_set_callback(self, config):
        """Test setting press callback for key monitor."""
        monitor = KeyMonitor(config)

        def callback():
            """Test callback function."""
            return None

        monitor.set_callback(callback)
        assert monitor._callback == callback

    def test_set_release_callback(self, config):
        """Test setting release callback for key monitor."""
        monitor = KeyMonitor(config)

        def release_callback():
            """Test release callback function."""
            return None

        monitor.set_release_callback(release_callback)
        assert monitor._release_callback == release_callback

    def test_start_monitoring_success(self, config, mock_listener):
        """Test successful start of key monitoring."""
        monitor = KeyMonitor(config)

        monitor.start_monitoring()

        assert monitor.is_monitoring()
        mock_listener.start.assert_called_once()

    def test_start_monitoring_already_active(self, config, mock_listener):
        """Test starting monitoring when already active."""
        monitor = KeyMonitor(config)
        monitor._monitoring = True

        monitor.start_monitoring()

        # Should not call start again
        mock_listener.start.assert_not_called()

    def test_start_monitoring_failure(self, config):
        """Test handling of monitoring start failure."""
        with patch(
            "whisper_claude.key_monitor.keyboard.Listener"
        ) as mock_listener_class:
            mock_listener_class.side_effect = Exception("Listener failed")

            monitor = KeyMonitor(config)

            with pytest.raises(KeyMonitorError, match="Failed to start key monitoring"):
                monitor.start_monitoring()

    def test_stop_monitoring(self, config, mock_listener):
        """Test stopping key monitoring."""
        monitor = KeyMonitor(config)
        monitor._listener = mock_listener
        monitor._monitoring = True

        monitor.stop_monitoring()

        assert not monitor.is_monitoring()
        mock_listener.stop.assert_called_once()

    def test_stop_monitoring_not_active(self, config):
        """Test stopping monitoring when not active."""
        monitor = KeyMonitor(config)

        # Should not raise any errors
        monitor.stop_monitoring()
        assert not monitor.is_monitoring()

    def test_normalize_key_special_keys(self, config):
        """Test key normalization for special keys."""
        monitor = KeyMonitor(config)

        # Test special key normalization
        mock_key = Mock()
        mock_key.name = "ctrl"
        assert monitor._normalize_key(mock_key) == "ctrl"

        mock_key.name = "SPACE"
        assert monitor._normalize_key(mock_key) == "space"

    def test_normalize_key_character_keys(self, config):
        """Test key normalization for character keys."""
        monitor = KeyMonitor(config)

        # Test character key normalization
        mock_key = Mock()
        mock_key.char = "A"
        del mock_key.name  # Character keys don't have name
        assert monitor._normalize_key(mock_key) == "a"

        mock_key.char = "1"
        assert monitor._normalize_key(mock_key) == "1"

    def test_normalize_key_unknown(self, config):
        """Test key normalization for unknown keys."""
        monitor = KeyMonitor(config)

        # Test unknown key
        mock_key = Mock()
        del mock_key.name
        del mock_key.char
        assert monitor._normalize_key(mock_key) is None

    def test_hotkey_detection_press_release(self, config):
        """Test hotkey detection with press and release events."""
        monitor = KeyMonitor(config)
        press_callback = Mock()
        release_callback = Mock()

        monitor.set_callback(press_callback)
        monitor.set_release_callback(release_callback)

        # Simulate pressing hotkey combination
        monitor._pressed_keys.add("ctrl")
        monitor._pressed_keys.add("alt")
        monitor._check_hotkey_state()
        assert not monitor._hotkey_pressed  # Not all keys pressed yet

        monitor._pressed_keys.add("space")
        monitor._check_hotkey_state()

        # Allow time for callback thread
        time.sleep(0.1)
        assert monitor._hotkey_pressed
        press_callback.assert_called_once()

        # Simulate releasing a key
        monitor._pressed_keys.remove("space")
        monitor._check_hotkey_state()

        # Allow time for callback thread
        time.sleep(0.1)
        assert not monitor._hotkey_pressed
        release_callback.assert_called_once()

    def test_is_hotkey_pressed(self, config):
        """Test checking if hotkey is currently pressed."""
        monitor = KeyMonitor(config)

        assert not monitor.is_hotkey_pressed()

        monitor._hotkey_pressed = True
        assert monitor.is_hotkey_pressed()

    def test_get_pressed_keys(self, config):
        """Test getting currently pressed keys."""
        monitor = KeyMonitor(config)

        # Initially empty
        assert monitor.get_pressed_keys() == set()

        # Add some keys
        monitor._pressed_keys.add("ctrl")
        monitor._pressed_keys.add("space")

        pressed = monitor.get_pressed_keys()
        assert pressed == {"ctrl", "space"}

        # Should return a copy
        pressed.add("alt")
        assert monitor._pressed_keys == {"ctrl", "space"}

    def test_on_key_press_valid_key(self, config):
        """Test handling key press events."""
        monitor = KeyMonitor(config)

        # Mock key with name attribute
        mock_key = Mock()
        mock_key.name = "ctrl"

        monitor._on_key_press(mock_key)

        assert "ctrl" in monitor._pressed_keys

    def test_on_key_press_invalid_key(self, config):
        """Test handling invalid key press events."""
        monitor = KeyMonitor(config)

        # Mock key that will return None from normalize
        mock_key = Mock()
        del mock_key.name
        del mock_key.char

        # Should not raise an error
        monitor._on_key_press(mock_key)
        assert len(monitor._pressed_keys) == 0

    def test_on_key_release_valid_key(self, config):
        """Test handling key release events."""
        monitor = KeyMonitor(config)
        monitor._pressed_keys.add("ctrl")

        # Mock key with name attribute
        mock_key = Mock()
        mock_key.name = "ctrl"

        monitor._on_key_release(mock_key)

        assert "ctrl" not in monitor._pressed_keys

    def test_callback_error_handling(self, config):
        """Test error handling in callbacks."""
        monitor = KeyMonitor(config)

        # Create callback that raises an error
        def failing_callback():
            raise Exception("Callback error")

        monitor.set_callback(failing_callback)

        # Should not raise an error when callback fails
        monitor._pressed_keys.update({"ctrl", "alt", "space"})
        monitor._check_hotkey_state()

    def test_close(self, config, mock_listener):
        """Test key monitor cleanup."""
        monitor = KeyMonitor(config)
        monitor._listener = mock_listener
        monitor._monitoring = True

        monitor.close()

        assert not monitor.is_monitoring()
        mock_listener.stop.assert_called_once()

    def test_create_key_monitor(self, config):
        """Test create_key_monitor factory function."""
        monitor = create_key_monitor(config)

        assert isinstance(monitor, KeyMonitor)
        assert monitor.config == config
