"""Status indicator tests."""

import io
import unittest.mock

from whisper_wayland.application.status_indicator import StatusIndicator


class TestStatusIndicator:
    """Test desktop status indicator command output."""

    def test_recording_updates_icon_and_text(self) -> None:
        """Test recording state writes mic commands."""
        process = unittest.mock.Mock()
        process.stdin = io.StringIO()
        process.poll.return_value = None
        indicator = StatusIndicator(process=process)

        indicator.recording()

        output = process.stdin.getvalue()
        assert "visible:true" in output
        assert f"icon:{StatusIndicator.RECORDING_ICON}" in output
        assert "message:Recording" in output

    def test_error_stops_spinner_and_updates_warning_icon(self) -> None:
        """Test error state writes warning commands."""
        process = unittest.mock.Mock()
        process.stdin = io.StringIO()
        process.poll.return_value = None
        indicator = StatusIndicator(process=process)

        indicator.error("Transcription failed")

        output = process.stdin.getvalue()
        assert f"icon:{StatusIndicator.ERROR_ICON}" in output
        assert "message:Transcription failed" in output

    def test_idle_hides_indicator(self) -> None:
        """Test idle state hides indicator."""
        process = unittest.mock.Mock()
        process.stdin = io.StringIO()
        process.poll.return_value = None

        StatusIndicator(process=process)

        assert "visible:false" in process.stdin.getvalue()
