"""Unit tests for key monitor module with evdev implementation."""

import os
import threading
import time
from unittest.mock import Mock, patch, MagicMock

import pytest

from whisper_claude.config import Config
from whisper_claude.key_monitor import KeyMonitor, KeyMonitorError, create_key_monitor


class TestKeyMonitor:
    """Test cases for KeyMonitor class with evdev implementation."""

    @pytest.fixture
    def config(self, mock_api_key):
        """Create test configuration."""
        with patch.dict(os.environ, {"HOTKEY": "compose"}):
            return Config()

    @pytest.fixture
    def mock_evdev_devices(self):
        """Create mock evdev devices."""
        mock_device1 = Mock()
        mock_device1.name = "Test Keyboard 1"
        mock_device1.path = "/dev/input/event0"
        mock_device1.fd = 10
        mock_device1.capabilities.return_value = {
            1: [1, 2, 3, 28, 57]  # EV_KEY with some key codes including space
        }
        mock_device1.read.return_value = []
        mock_device1.close = Mock()

        mock_device2 = Mock()
        mock_device2.name = "Test Keyboard 2"
        mock_device2.path = "/dev/input/event1"
        mock_device2.fd = 11
        mock_device2.capabilities.return_value = {
            1: [1, 2, 3, 28, 57]  # EV_KEY with some key codes including space
        }
        mock_device2.read.return_value = []
        mock_device2.close = Mock()

        return [mock_device1, mock_device2]

    @pytest.fixture
    def mock_evdev(self, mock_evdev_devices):
        """Mock evdev module."""
        with patch("whisper_claude.key_monitor.evdev") as mock_evdev:
            # Mock list_devices to return device paths
            mock_evdev.list_devices.return_value = [
                "/dev/input/event0",
                "/dev/input/event1"
            ]
            
            # Mock InputDevice constructor to return our mock devices
            mock_evdev.InputDevice.side_effect = mock_evdev_devices
            
            # Mock ecodes constants
            mock_evdev.ecodes.EV_KEY = 1
            mock_evdev.ecodes.KEY_SPACE = 57
            mock_evdev.ecodes.KEY_ENTER = 28
            mock_evdev.ecodes.KEY_COMPOSE = 127
            
            yield mock_evdev

    def test_key_monitor_initialization(self, config):
        """Test key monitor initialization with valid config."""
        monitor = KeyMonitor(config)

        assert monitor.config == config
        assert monitor._callback is None
        assert monitor._release_callback is None
        assert not monitor._monitoring
        assert not monitor._hotkey_pressed
        assert monitor._hotkey_combination == {"compose"}

    def test_key_monitor_initialization_custom_hotkey(self, mock_api_key):
        """Test key monitor initialization with custom hotkey."""
        with patch.dict(os.environ, {"HOTKEY": "ctrl+shift+f1"}):
            config = Config()
            monitor = KeyMonitor(config)

            assert monitor._hotkey_combination == {"ctrl", "shift", "f1"}

    def test_key_monitor_initialization_single_key(self, mock_api_key):
        """Test key monitor initialization with single key."""
        with patch.dict(os.environ, {"HOTKEY": "f10"}):
            config = Config()
            monitor = KeyMonitor(config)

            assert monitor._hotkey_combination == {"f10"}

    def test_key_monitor_initialization_invalid_hotkey(self, mock_api_key):
        """Test key monitor initialization with invalid hotkey."""
        with patch.dict(os.environ, {"HOTKEY": ""}):
            config = Config()
            with pytest.raises(KeyMonitorError, match="Hotkey cannot be empty"):
                KeyMonitor(config)

    def test_parse_hotkey_combination_various_formats(self, mock_api_key):
        """Test hotkey parsing with various input formats."""
        test_cases = [
            ("compose", {"compose"}),
            ("ctrl+space", {"ctrl", "space"}),
            ("ctrl+alt+space", {"ctrl", "alt", "space"}),
            ("shift+a", {"shift", "a"}),
            ("ctrl+shift+enter", {"ctrl", "shift", "enter"}),
            ("f5", {"f5"}),
            ("menu", {"menu"}),
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

    def test_build_key_map(self, config):
        """Test building of key code mapping."""
        monitor = KeyMonitor(config)
        key_map = monitor._key_map

        # Test some expected mappings
        assert key_map[57] == "space"  # KEY_SPACE
        assert key_map[28] == "enter"  # KEY_ENTER
        assert key_map[127] == "compose"  # KEY_COMPOSE
        
        # Test letter keys
        assert key_map[30] == "a"  # KEY_A
        assert key_map[48] == "b"  # KEY_B
        
        # Test number keys
        assert key_map[2] == "1"  # KEY_1
        assert key_map[11] == "0"  # KEY_0

    def test_get_key_name(self, config):
        """Test key name resolution."""
        monitor = KeyMonitor(config)

        # Test mapped keys
        assert monitor._get_key_name(57) == "space"
        assert monitor._get_key_name(28) == "enter"
        assert monitor._get_key_name(127) == "compose"

        # Test unmapped key
        assert monitor._get_key_name(999) is None

    @patch("whisper_claude.key_monitor.select.select")
    def test_start_monitoring_success(self, mock_select, config, mock_evdev):
        """Test successful start of key monitoring."""
        mock_select.return_value = ([], [], [])
        
        monitor = KeyMonitor(config)
        monitor.start_monitoring()

        assert monitor.is_monitoring()
        assert len(monitor._devices) == 2  # Two mock devices

    def test_start_monitoring_already_active(self, config, mock_evdev):
        """Test starting monitoring when already active."""
        monitor = KeyMonitor(config)
        monitor._monitoring = True

        # Should not raise an error
        monitor.start_monitoring()
        assert monitor.is_monitoring()

    def test_start_monitoring_no_devices(self, config):
        """Test handling when no devices are found."""
        with patch("whisper_claude.key_monitor.evdev.list_devices", return_value=[]):
            monitor = KeyMonitor(config)
            
            with pytest.raises(KeyMonitorError, match="No keyboard devices found"):
                monitor.start_monitoring()

    def test_start_monitoring_permission_error(self, config):
        """Test handling of permission errors."""
        with patch("whisper_claude.key_monitor.evdev.list_devices", 
                  side_effect=PermissionError("Access denied")):
            monitor = KeyMonitor(config)
            
            with pytest.raises(KeyMonitorError, match="Permission denied"):
                monitor.start_monitoring()

    def test_stop_monitoring(self, config, mock_evdev):
        """Test stopping key monitoring."""
        with patch("whisper_claude.key_monitor.select.select", 
                  return_value=([], [], [])):
            monitor = KeyMonitor(config)
            monitor.start_monitoring()
            
            assert monitor.is_monitoring()
            
            monitor.stop_monitoring()
            
            assert not monitor.is_monitoring()
            assert len(monitor._devices) == 0

    def test_stop_monitoring_not_active(self, config):
        """Test stopping monitoring when not active."""
        monitor = KeyMonitor(config)

        # Should not raise any errors
        monitor.stop_monitoring()
        assert not monitor.is_monitoring()

    def test_check_hotkey_state_press_release(self, config):
        """Test hotkey state detection with press and release."""
        monitor = KeyMonitor(config)
        press_callback = Mock()
        release_callback = Mock()

        monitor.set_callback(press_callback)
        monitor.set_release_callback(release_callback)

        # Simulate pressing compose key
        with monitor._lock:
            monitor._pressed_keys.add("compose")
            monitor._check_hotkey_state()

        # Small delay to allow callback thread to execute
        time.sleep(0.1)
        assert monitor._hotkey_pressed
        press_callback.assert_called_once()

        # Simulate releasing compose key
        with monitor._lock:
            monitor._pressed_keys.remove("compose")
            monitor._check_hotkey_state()

        # Small delay to allow callback thread to execute
        time.sleep(0.1)
        assert not monitor._hotkey_pressed
        release_callback.assert_called_once()

    def test_check_hotkey_state_combination(self, mock_api_key):
        """Test hotkey state with key combination."""
        with patch.dict(os.environ, {"HOTKEY": "ctrl+alt"}):
            config = Config()
            monitor = KeyMonitor(config)
            press_callback = Mock()

            monitor.set_callback(press_callback)

            # Press only ctrl - should not trigger
            with monitor._lock:
                monitor._pressed_keys.add("ctrl")
                monitor._check_hotkey_state()

            assert not monitor._hotkey_pressed
            press_callback.assert_not_called()

            # Press ctrl+alt - should trigger
            with monitor._lock:
                monitor._pressed_keys.add("alt")
                monitor._check_hotkey_state()

            time.sleep(0.1)
            assert monitor._hotkey_pressed
            press_callback.assert_called_once()

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

    def test_callback_error_handling(self, config):
        """Test error handling in callbacks."""
        monitor = KeyMonitor(config)

        # Create callback that raises an error
        def failing_callback():
            raise Exception("Callback error")

        monitor.set_callback(failing_callback)

        # Should not raise an error when callback fails
        with monitor._lock:
            monitor._pressed_keys.add("compose")
            monitor._check_hotkey_state()

        # Allow time for callback thread
        time.sleep(0.1)

    def test_close(self, config, mock_evdev):
        """Test key monitor cleanup."""
        with patch("whisper_claude.key_monitor.select.select", 
                  return_value=([], [], [])):
            monitor = KeyMonitor(config)
            monitor.start_monitoring()
            
            assert monitor.is_monitoring()
            
            monitor.close()
            
            assert not monitor.is_monitoring()

    def test_create_key_monitor(self, config):
        """Test create_key_monitor factory function."""
        monitor = create_key_monitor(config)

        assert isinstance(monitor, KeyMonitor)
        assert monitor.config == config

    def test_device_cleanup(self, config, mock_evdev_devices):
        """Test device cleanup functionality."""
        monitor = KeyMonitor(config)
        monitor._devices = mock_evdev_devices.copy()

        monitor._cleanup_devices()

        # Check that all devices were closed
        for device in mock_evdev_devices:
            device.close.assert_called_once()

        assert len(monitor._devices) == 0

    def test_handle_key_event_press_release(self, config):
        """Test key event handling."""
        monitor = KeyMonitor(config)

        # Create mock event for key press
        press_event = Mock()
        press_event.type = 1  # EV_KEY
        press_event.code = 127  # KEY_COMPOSE
        press_event.value = 1  # Key press

        # Handle press event
        monitor._handle_key_event(press_event)
        assert "compose" in monitor._pressed_keys

        # Create mock event for key release
        release_event = Mock()
        release_event.type = 1  # EV_KEY
        release_event.code = 127  # KEY_COMPOSE
        release_event.value = 0  # Key release

        # Handle release event
        monitor._handle_key_event(release_event)
        assert "compose" not in monitor._pressed_keys