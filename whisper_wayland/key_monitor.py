"""Whisper Wayland - Key Monitor (Compatibility Module)

Imports the modularized KeyMonitor class for backward compatibility.
"""

# Import from the new modular structure
from whisper_wayland.key_monitor.key_monitor import KeyMonitor, KeyMonitorError  # noqa: F401 I001
