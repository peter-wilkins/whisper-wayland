"""Continuum capture tap tests."""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import struct
import unittest.mock
import wave
from datetime import datetime, timezone
from pathlib import Path

import pytest

import whisper_wayland as ww
from whisper_wayland.application.capture_tap import CaptureTap
from whisper_wayland.application.transcription_processor import TranscriptionProcessor

TEST_SAMPLE_RATE = 16000
TEST_FRAME_COUNT = 1600
TEST_DURATION_SECONDS = 0.1
CLIPPED_SAMPLE = 32767
FULL_CLIPPING_RATIO = 1.0


def _test_wav(sample_rate: int = TEST_SAMPLE_RATE, frame_count: int = TEST_FRAME_COUNT) -> bytes:
    """Build a tiny valid mono PCM WAV."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return buffer.getvalue()


def _constant_wav(sample: int) -> bytes:
    buffer = io.BytesIO()
    payload = struct.pack(f"<{TEST_FRAME_COUNT}h", *([sample] * TEST_FRAME_COUNT))
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(TEST_SAMPLE_RATE)
        wav_file.writeframes(payload)
    return buffer.getvalue()


def _fixed_clock() -> datetime:
    return datetime(2026, 5, 23, 9, 15, 30, 123000, tzinfo=timezone.utc)


class TestCaptureTap:
    """Test Continuum capture tap file-drop behavior."""

    def test_disabled_when_inlet_dir_unset(self, tmp_path: Path) -> None:
        """Unset CONTINUUM_CAPTURE_INLET_DIR leaves behavior disabled."""
        with unittest.mock.patch.dict(
            os.environ,
            {"OPENAI_API_KEY": "sk-test123"},
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            tap = CaptureTap(test_config, clock=_fixed_clock)

            result = tap.write(_test_wav(), "raw text", "insert text")

        assert result is None
        assert not (tmp_path / "artifacts").exists()
        assert not (tmp_path / "envelopes").exists()

    def test_enabled_tap_writes_artifact_and_envelope(self, tmp_path: Path) -> None:
        """Enabled tap writes WAV artifact and JSON envelope."""
        audio_data = _test_wav()

        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "CONTINUUM_CAPTURE_INLET_DIR": str(tmp_path),
                "WHISPER_MODEL": "whisper-1",
                "TEXT_POST_PROCESS_MODE": "caveman",
                "TEXT_POST_PROCESS_MODEL": "local",
                "AUDIO_INPUT_DEVICE_NAME": "alsa_input.pci",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            tap = CaptureTap(test_config, clock=_fixed_clock)

            result = tap.write(audio_data, "raw transcript", "Insert transcript.")

        assert result is not None
        assert result.artifact_path.read_bytes() == audio_data
        assert result.envelope_path.exists()
        assert not Path(f"{result.envelope_path}.tmp").exists()

        envelope = json.loads(result.envelope_path.read_text(encoding="utf-8"))
        assert envelope["schemaVersion"] == "continuum.audio-capture-tap.v1"
        assert re.match(
            rf"^whisper-wayland:20260523T091530123Z:{os.getpid()}:\d{{4}}$",
            envelope["captureId"],
        )
        assert envelope["sourceTool"]["name"] == "whisper-wayland"
        assert envelope["sourceTool"]["repoPath"] == str(Path.cwd())
        assert envelope["captureTap"] == {
            "point": "after_batch_transcription_before_text_insertion",
            "createdAt": "2026-05-23T09:15:30.123Z",
        }

        artifact = envelope["audioArtifact"]
        assert artifact["relativePath"].startswith(
            "artifacts/2026-05-23/whisper-wayland-20260523T091530123Z-"
        )
        assert (tmp_path / artifact["relativePath"]).read_bytes() == audio_data
        assert artifact["mimeType"] == "audio/wav"
        assert artifact["codec"] == "pcm_s16le"
        assert artifact["sampleRateHz"] == TEST_SAMPLE_RATE
        assert artifact["channelCount"] == 1
        assert artifact["durationSeconds"] == TEST_DURATION_SECONDS
        assert artifact["byteLength"] == len(audio_data)
        assert artifact["sha256"] == hashlib.sha256(audio_data).hexdigest()

        health = envelope["captureHealth"]
        assert health["durationSeconds"] == TEST_DURATION_SECONDS
        assert health["byteLength"] == len(audio_data)
        assert health["rmsAmplitude"] == 0
        assert health["peakAmplitude"] == 0
        assert health["clippingRatio"] == 0
        assert health["likelySilent"] is True
        assert health["likelyClipped"] is False
        assert health["checks"][0]["kind"] == "rms_level"
        assert health["checks"][0]["status"] == "fail"
        assert health["checks"][1]["kind"] == "clipping"
        assert health["checks"][1]["status"] == "pass"

        assert envelope["transcript"] == {
            "rawTranscriptText": "raw transcript",
            "insertionText": "Insert transcript.",
            "postProcessMode": "caveman",
        }
        assert envelope["captureContext"]["captureInlet"] == "local-file-drop"
        assert envelope["captureContext"]["deviceLabel"] == "alsa_input.pci"
        assert envelope["captureContext"]["membraneDecision"] == "accepted"
        assert envelope["captureContext"]["contextClues"][0]["text"] == (
            "push-to-talk hotkey released"
        )
        assert envelope["processor"]["provider"] == "openai"
        assert envelope["processor"]["processorId"] == "whisper-1"
        assert envelope["processor"]["processorKind"] == "transcription"
        assert re.match(
            r"^[0-9a-f]{16}$",
            envelope["processor"]["configurationFingerprint"],
        )

    def test_envelope_write_uses_tmp_then_rename(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Envelope commit point is a tmp file rename."""
        replace_calls = []
        original_replace = Path.replace

        def spy_replace(self: Path, target: Path | str) -> Path:
            if str(self).endswith(".json.tmp"):
                target_path = Path(target)
                replace_calls.append((self.exists(), target_path.exists()))
            return original_replace(self, target)

        monkeypatch.setattr(Path, "replace", spy_replace)

        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "CONTINUUM_CAPTURE_INLET_DIR": str(tmp_path),
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            tap = CaptureTap(test_config, clock=_fixed_clock)

            result = tap.write(_test_wav(), "raw", "insert")

        assert result is not None
        assert replace_calls == [(True, False)]
        assert result.envelope_path.exists()
        assert not list((tmp_path / "envelopes").glob("*.tmp"))

    def test_clipped_capture_is_still_written_with_health_flags(self, tmp_path: Path) -> None:
        """Clipped captures are marked, not dropped."""
        audio_data = _constant_wav(CLIPPED_SAMPLE)

        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "CONTINUUM_CAPTURE_INLET_DIR": str(tmp_path),
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            tap = CaptureTap(test_config, clock=_fixed_clock)

            result = tap.write(audio_data, "raw", "insert")

        assert result is not None
        envelope = json.loads(result.envelope_path.read_text(encoding="utf-8"))
        health = envelope["captureHealth"]
        assert result.artifact_path.exists()
        assert health["likelySilent"] is False
        assert health["likelyClipped"] is True
        assert health["clippingRatio"] == FULL_CLIPPING_RATIO
        assert health["checks"][1]["status"] == "fail"

    def test_processor_writes_capture_before_text_insertion(self, tmp_path: Path) -> None:
        """Batch processor preserves raw transcript and writes tap before insertion."""
        audio_data = _test_wav()
        insert_calls = []

        class RecordingTextInserter:
            def insert_text(self, text: str) -> bool:
                insert_calls.append((text, list((tmp_path / "envelopes").glob("*.json"))))
                return True

        with unittest.mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test123",
                "CONTINUUM_CAPTURE_INLET_DIR": str(tmp_path),
                "WHISPER_MODEL": "whisper-1",
                "TEXT_POST_PROCESS_MODE": "caveman",
                "TEXT_POST_PROCESS_MODEL": "local",
            },
            clear=True,
        ):
            test_config = ww.Config("/nonexistent/test.env")
            transcription_client = unittest.mock.Mock()
            transcription_client.config = test_config
            transcription_client.transcribe_audio.return_value = "uh raw raw transcript"
            transcription_client.post_process_text.return_value = "Raw transcript"
            processor = TranscriptionProcessor(transcription_client, RecordingTextInserter())

            processor.process_audio(audio_data)

        assert insert_calls
        assert insert_calls[0][0] == "Raw transcript"
        assert insert_calls[0][1]

        envelope_path = insert_calls[0][1][0]
        envelope = json.loads(envelope_path.read_text(encoding="utf-8"))
        assert envelope["transcript"]["rawTranscriptText"] == "uh raw raw transcript"
        assert envelope["transcript"]["insertionText"] == "Raw transcript"
