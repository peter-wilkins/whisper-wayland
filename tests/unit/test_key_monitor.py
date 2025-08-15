"""Unit tests for key monitor module (placeholder for Step 2)."""

import os
from unittest.mock import patch
import pytest

from whisper_claude.config import Config
from whisper_claude.key_monitor import KeyMonitor, create_key_monitor


class TestKeyMonitor:
    """Test cases for KeyMonitor placeholder class."""

    @pytest.fixture
    def config(self):
        """Create test configuration."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test123"}):
            return Config()

    def test_key_monitor_initialization(self, config):
        """Test key monitor placeholder initialization."""
        monitor = KeyMonitor(config)
        
        assert monitor.config == config
        assert monitor._callback is None

    def test_set_callback(self, config):
        """Test setting callback for key monitor."""
        monitor = KeyMonitor(config)
        callback = lambda: None
        
        monitor.set_callback(callback)
        
        assert monitor._callback == callback

    def test_start_monitoring(self, config):
        """Test start monitoring placeholder."""
        monitor = KeyMonitor(config)
        
        # Should not raise any errors
        monitor.start_monitoring()

    def test_stop_monitoring(self, config):
        """Test stop monitoring placeholder."""
        monitor = KeyMonitor(config)
        
        # Should not raise any errors
        monitor.stop_monitoring()

    def test_is_monitoring(self, config):
        """Test monitoring status check."""
        monitor = KeyMonitor(config)
        
        # Placeholder always returns False
        assert monitor.is_monitoring() is False

    def test_close(self, config):
        """Test key monitor cleanup."""
        monitor = KeyMonitor(config)
        
        # Should not raise any errors
        monitor.close()

    def test_create_key_monitor(self, config):
        """Test create_key_monitor factory function."""
        monitor = create_key_monitor(config)
        
        assert isinstance(monitor, KeyMonitor)
        assert monitor.config == config