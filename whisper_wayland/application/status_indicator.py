"""Optional desktop status indicator for recording and transcription state."""

import itertools
import logging
import shutil
import subprocess
import threading
import time
import typing

_logger = logging.getLogger(__name__)


class StatusIndicator:
    """Controls an optional desktop notification/tray indicator when enabled."""

    IDLE_ICON = "dialog-information-symbolic"
    RECORDING_ICON = "audio-input-microphone-symbolic"
    TRANSCRIBING_ICON = "process-working-symbolic"
    ERROR_ICON = "dialog-warning-symbolic"
    SPINNER_FRAMES = ("-", "\\", "|", "/")

    def __init__(
        self,
        process: typing.Optional[subprocess.Popen[str]] = None,
        start_process: bool = False,
    ) -> None:
        """Initialize status indicator.

        Args:
            process: Optional process for tests.
            start_process: Whether to launch zenity when process is not provided.
        """
        self._process = process
        self._lock = threading.Lock()
        self._spinner_stop = threading.Event()
        self._spinner_thread: typing.Optional[threading.Thread] = None
        self._available = process is not None

        if process is None and start_process:
            self._process = self._start_zenity()
            self._available = self._process is not None

        self.idle()

    def recording(self) -> None:
        """Show active recording state."""
        self._stop_spinner()
        self._set_state(self.RECORDING_ICON, "Recording")

    def transcribing(self) -> None:
        """Show active transcription state."""
        self._set_state(self.TRANSCRIBING_ICON, "Transcribing")
        self._start_spinner()

    def error(self, message: str = "Whisper Wayland needs attention") -> None:
        """Show an error or blocked state."""
        self._stop_spinner()
        self._set_state(self.ERROR_ICON, message)

    def idle(self) -> None:
        """Hide the indicator while idle."""
        self._stop_spinner()
        self._send("visible:false")

    def close(self) -> None:
        """Close the indicator process."""
        self._stop_spinner()
        if self._process:
            try:
                self._send("visible:false")
                self._process.terminate()
            except Exception as e:
                _logger.debug(f"Error closing status indicator: {e}")

    def _start_zenity(self) -> typing.Optional[subprocess.Popen[str]]:
        """Start zenity notification listener if available."""
        zenity = shutil.which("zenity")
        if not zenity:
            _logger.debug("zenity not available; status indicator disabled")
            return None

        try:
            return subprocess.Popen(
                [
                    zenity,
                    "--notification",
                    "--listen",
                    "--text=Whisper Wayland",
                    f"--icon={self.IDLE_ICON}",
                ],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except Exception as e:
            _logger.debug(f"Could not start status indicator: {e}")
            return None

    def _set_state(self, icon: str, text: str) -> None:
        """Update icon and text."""
        self._send("visible:true")
        self._send(f"icon:{icon}")
        self._send(f"tooltip:{text}")
        self._send(f"message:{text}")

    def _start_spinner(self) -> None:
        """Start cycling transcription status text."""
        self._stop_spinner()
        self._spinner_stop = threading.Event()
        self._spinner_thread = threading.Thread(target=self._spinner_loop, daemon=True)
        self._spinner_thread.start()

    def _stop_spinner(self) -> None:
        """Stop active spinner thread."""
        self._spinner_stop.set()
        if self._spinner_thread and self._spinner_thread.is_alive():
            self._spinner_thread.join(timeout=0.5)
        self._spinner_thread = None

    def _spinner_loop(self) -> None:
        """Cycle a lightweight spinner in the indicator text."""
        for frame in itertools.cycle(self.SPINNER_FRAMES):
            if self._spinner_stop.is_set():
                return
            self._set_state(self.TRANSCRIBING_ICON, f"Transcribing {frame}")
            time.sleep(0.25)

    def _send(self, command: str) -> None:
        """Send a command to the zenity notification listener."""
        if not self._available or not self._process or not self._process.stdin:
            return

        with self._lock:
            if self._process.poll() is not None:
                self._available = False
                return
            try:
                self._process.stdin.write(f"{command}\n")
                self._process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                self._available = False
                _logger.debug(f"Status indicator unavailable: {e}")

    @staticmethod
    def new() -> "StatusIndicator":
        """Create status indicator instance."""
        return StatusIndicator()
