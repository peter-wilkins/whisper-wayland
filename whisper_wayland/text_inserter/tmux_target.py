"""Track tmux insertion targets captured at recording start."""

import logging
import os
import re
from pathlib import Path

_logger = logging.getLogger(__name__)

_TMUX_PANE_ID = re.compile(r"^%\d+$")


def default_active_pane_file() -> str:
    """Return the default file used by tmux hooks to expose the active pane."""
    runtime_dir = os.getenv("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}"
    return str(Path(runtime_dir) / "whisper-wayland" / "active-tmux-pane")


class TmuxTargetCapture:
    """Reads the active tmux pane written by the tmux hook installer."""

    def __init__(self, enabled: bool, active_pane_file: str) -> None:
        self._enabled = enabled
        self._active_pane_file = active_pane_file

    def capture(self) -> str | None:
        """Return the active tmux pane id, or None when unavailable."""
        if not self._enabled:
            return None

        path = Path(self._active_pane_file).expanduser()
        try:
            pane_id = path.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            _logger.debug("No active tmux pane file found at %s", path)
            return None
        except OSError as e:
            _logger.warning("Could not read active tmux pane file %s: %s", path, e)
            return None

        if not _TMUX_PANE_ID.fullmatch(pane_id):
            _logger.warning("Ignoring invalid tmux pane id from %s: %r", path, pane_id)
            return None

        _logger.info("Captured tmux insertion target: %s", pane_id)
        return pane_id

    @staticmethod
    def new(enabled: bool, active_pane_file: str) -> "TmuxTargetCapture":
        return TmuxTargetCapture(enabled, active_pane_file)
