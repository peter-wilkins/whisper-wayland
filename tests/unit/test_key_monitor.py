"""Unit tests for key monitor module with evdev implementation."""

import os
import time
import unittest.mock

import pytest

from whisper_wayland import config, constants, key_monitor


class TestKeyMonitor:
    """Test cases for KeyMonitor class with evdev implementation."""

    @pytest.fixture
    def test_config(self, mock_api_key):
        """Create test configuration."""
        with unittest.mock.unittest.mock.patch.dict(os.environ, {"HOTKEY": "compose"}):
            return config.config.Config()

    @pytest.fixture
    def mock_evdev_devices(self):
        """Create mock evdev devices."""
        mock_device1 = unittest.mock.unittest.mock.Mock()
        mock_device1.name = "Test Keyboard 1"
        mock_device1.path = "/dev/input/event0"
        mock_device1.fd = 10
        mock_device1.capabilities.return_value = {
            1: [1, 2, 3, 28, 57]  # EV_KEY with some key codes including space
        }
        mock_device1.read.return_value = []
        mock_device1.close = unittest.mock.unittest.mock.Mock()

        mock_device2 = unittest.mock.unittest.mock.Mock()
        mock_device2.name = "Test Keyboard 2"
        mock_device2.path = "/dev/input/event1"
        mock_device2.fd = 11
        mock_device2.capabilities.return_value = {
            1: [1, 2, 3, 28, 57]  # EV_KEY with some key codes including space
        }
        mock_device2.read.return_value = []
        mock_device2.close = unittest.mock.unittest.mock.Mock()

        return [mock_device1, mock_device2]

    @pytest.fixture
    def mock_evdev(self, mock_evdev_devices):
        """Mock evdev module."""
        with unittest.mock.patch("whisper_wayland.key_monitor.evdev") as mock_evdev:
            # Mock list_devices to return device paths
            mock_evdev.list_devices.return_value = [
                "/dev/input/event0",
                "/dev/input/event1",
            ]

            # Mock InputDevice constructor to return our mock devices
            mock_evdev.InputDevice.side_effect = mock_evdev_devices

            # Mock ecodes constants
            mock_evdev.ecodes.EV_KEY = 1
            mock_evdev.ecodes.KEY_SPACE = 57
            mock_evdev.ecodes.KEY_ENTER = 28
            mock_evdev.ecodes.KEY_COMPOSE = 127

            yield mock_evdev

    def test_key_monitor_initialization(self, test_config):
        """Test key monitor initialization with valid config."""
        monitor = key_monitor.KeyMonitor(test_config)

        assert monitor.config == test_config
        assert monitor._callback is None
        assert monitor._release_callback is None
        assert not monitor._monitoring
        assert not monitor._hotkey_pressed
        assert monitor._hotkey_combination == {"ctrl", "compose"}

    def test_key_monitor_initialization_custom_hotkey(self, mock_api_key):
        """Test key monitor initialization with custom hotkey."""
        with unittest.mock.patch.dict(os.environ, {"HOTKEY": "ctrl+shift+f1"}):
            hotkey_config = config.Config()
            monitor = key_monitor.KeyMonitor(hotkey_config)

            assert monitor._hotkey_combination == {"ctrl", "shift", "f1"}

    def test_key_monitor_initialization_single_key(self, mock_api_key):
        """Test key monitor initialization with single key."""
        with unittest.mock.patch.dict(os.environ, {"HOTKEY": "f10"}):
            f10_config = config.Config()
            monitor = key_monitor.KeyMonitor(f10_config)

            assert monitor._hotkey_combination == {"f10"}

    def test_key_monitor_initialization_invalid_hotkey(self, mock_api_key):
        """Test key monitor initialization with invalid hotkey."""
        with unittest.mock.patch.dict(os.environ, {"HOTKEY": ""}):
            empty_config = config.Config()
            with pytest.raises(key_monitor.KeyMonitorError, match="Hotkey cannot be empty"):
                key_monitor.KeyMonitor(empty_config)

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
            with unittest.mock.patch.dict(os.environ, {"HOTKEY": hotkey_str}):
                test_hotkey_config = config.Config()
                monitor = key_monitor.KeyMonitor(test_hotkey_config)
                assert monitor._hotkey_combination == expected

    def test_set_callback(self, test_config):
        """Test setting press callback for key monitor."""
        monitor = key_monitor.KeyMonitor(test_config)

        def callback():
            """Test callback function."""
            return None

        monitor.set_callback(callback)
        assert monitor._callback == callback

    def test_set_release_callback(self, test_config):
        """Test setting release callback for key monitor."""
        monitor = key_monitor.KeyMonitor(test_config)

        def release_callback():
            """Test release callback function."""
            return None

        monitor.set_release_callback(release_callback)
        assert monitor._release_callback == release_callback

    def test_build_key_map(self, test_config):
        """Test building of key code mapping."""
        monitor = key_monitor.KeyMonitor(test_config)
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

    def test_get_key_name(self, test_config):
        """Test key name resolution."""
        monitor = key_monitor.KeyMonitor(test_config)

        # Test mapped keys
        assert monitor._get_key_name(57) == "space"
        assert monitor._get_key_name(28) == "enter"
        assert monitor._get_key_name(127) == "compose"

        # Test unmapped key
        assert monitor._get_key_name(999) is None

    @unittest.mock.patch("whisper_wayland.key_monitor.select.select")
    def test_start_monitoring_success(self, mock_select, test_config, mock_evdev):
        """Test successful start of key monitoring."""
        mock_select.return_value = ([], [], [])

        monitor = key_monitor.KeyMonitor(test_config)
        monitor.start_monitoring()

        assert monitor.is_monitoring()
        assert len(monitor._devices) == constants.EXPECTED_DEVICE_COUNT  # Two mock devices

    def test_start_monitoring_already_active(self, test_config, mock_evdev):
        """Test starting monitoring when already active."""
        monitor = key_monitor.KeyMonitor(test_config)
        monitor._monitoring = True

        # Should not raise an error
        monitor.start_monitoring()
        assert monitor.is_monitoring()

    def test_start_monitoring_no_devices(self, test_config):
        """Test handling when no devices are found."""
        with unittest.mock.patch("whisper_wayland.key_monitor.evdev.list_devices", return_value=[]):
            monitor = key_monitor.KeyMonitor(test_config)

            with pytest.raises(key_monitor.KeyMonitorError, match="No keyboard devices found"):
                monitor.start_monitoring()

    def test_start_monitoring_permission_error(self, test_config):
        """Test handling of permission errors."""
        with unittest.mock.patch(
            "whisper_wayland.key_monitor.evdev.list_devices",
            side_effect=PermissionError("Access denied"),
        ):
            monitor = key_monitor.KeyMonitor(test_config)

            with pytest.raises(key_monitor.KeyMonitorError, match="Permission denied"):
                monitor.start_monitoring()

    def test_stop_monitoring(self, test_config, mock_evdev):
        """Test stopping key monitoring."""
        with unittest.mock.patch(
            "whisper_wayland.key_monitor.select.select", return_value=([], [], [])
        ):
            monitor = key_monitor.KeyMonitor(test_config)
            monitor.start_monitoring()

            assert monitor.is_monitoring()

            monitor.stop_monitoring()

            assert not monitor.is_monitoring()
            assert len(monitor._devices) == 0

    def test_stop_monitoring_not_active(self, test_config):
        """Test stopping monitoring when not active."""
        monitor = key_monitor.KeyMonitor(test_config)

        # Should not raise any errors
        monitor.stop_monitoring()
        assert not monitor.is_monitoring()

    def test_check_hotkey_state_press_release(self, test_config):
        """Test hotkey state detection with press and release."""
        monitor = key_monitor.KeyMonitor(test_config)
        press_callback = unittest.mock.Mock()
        release_callback = unittest.mock.Mock()

        monitor.set_callback(press_callback)
        monitor.set_release_callback(release_callback)

        # Simulate pressing ctrl+compose keys
        with monitor._lock:
            monitor._pressed_keys.add("ctrl")
            monitor._pressed_keys.add("compose")
            monitor._check_hotkey_state()

        # Small delay to allow callback thread to execute
        time.sleep(0.1)
        assert monitor._hotkey_pressed
        press_callback.assert_called_once()

        # Simulate releasing compose key (ctrl still held)
        with monitor._lock:
            monitor._pressed_keys.remove("compose")
            monitor._check_hotkey_state()

        # Small delay to allow callback thread to execute
        time.sleep(0.1)
        assert not monitor._hotkey_pressed
        release_callback.assert_called_once()

    def test_check_hotkey_state_combination(self, mock_api_key):
        """Test hotkey state with key combination."""
        with unittest.mock.patch.dict(os.environ, {"HOTKEY": "ctrl+alt"}):
            combo_config = config.Config()
            monitor = key_monitor.KeyMonitor(combo_config)
            press_callback = unittest.mock.Mock()

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

    def test_is_hotkey_pressed(self, test_config):
        """Test checking if hotkey is currently pressed."""
        monitor = key_monitor.KeyMonitor(test_config)

        assert not monitor.is_hotkey_pressed()

        monitor._hotkey_pressed = True
        assert monitor.is_hotkey_pressed()

    def test_get_pressed_keys(self, test_config):
        """Test getting currently pressed keys."""
        monitor = key_monitor.KeyMonitor(test_config)

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

    def test_callback_error_handling(self, test_config):
        """Test error handling in callbacks."""
        monitor = key_monitor.KeyMonitor(test_config)

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

    def test_close(self, test_config, mock_evdev):
        """Test key monitor cleanup."""
        with unittest.mock.patch(
            "whisper_wayland.key_monitor.select.select", return_value=([], [], [])
        ):
            monitor = key_monitor.KeyMonitor(test_config)
            monitor.start_monitoring()

            assert monitor.is_monitoring()

            monitor.close()

            assert not monitor.is_monitoring()

    def test_create_key_monitor(self, test_config):
        """Test create_key_monitor factory function."""
        monitor = key_monitor.create_key_monitor(test_config)

        assert isinstance(monitor, key_monitor.KeyMonitor)
        assert monitor.config == test_config

    def test_device_cleanup(self, test_config, mock_evdev_devices):
        """Test device cleanup functionality."""
        monitor = key_monitor.KeyMonitor(test_config)
        monitor._devices = mock_evdev_devices.copy()

        monitor._cleanup_devices()

        # Check that all devices were closed
        for device in mock_evdev_devices:
            device.close.assert_called_once()

        assert len(monitor._devices) == 0

    def test_handle_key_event_press_release(self, test_config):
        """Test key event handling."""
        monitor = key_monitor.KeyMonitor(test_config)

        # Create mock event for key press
        press_event = unittest.mock.Mock()
        press_event.type = 1  # EV_KEY
        press_event.code = 127  # KEY_COMPOSE
        press_event.value = 1  # Key press

        # Handle press event
        monitor._handle_key_event(press_event)
        assert "compose" in monitor._pressed_keys

        # Create mock event for key release
        release_event = unittest.mock.Mock()
        release_event.type = 1  # EV_KEY
        release_event.code = 127  # KEY_COMPOSE
        release_event.value = 0  # Key release

        # Handle release event
        monitor._handle_key_event(release_event)
        assert "compose" not in monitor._pressed_keys
