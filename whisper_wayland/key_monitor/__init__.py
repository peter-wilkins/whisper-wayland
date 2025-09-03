"""Whisper Wayland - Key Monitor Module

Key monitoring components for global hotkey detection using evdev.
"""

from whisper_wayland.key_monitor.key_monitor import KeyMonitor, KeyMonitorError

__all__ = ["KeyMonitor", "KeyMonitorError"]
