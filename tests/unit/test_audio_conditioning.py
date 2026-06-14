"""Tests for the local audio conditioning harness."""

from __future__ import annotations

import json
import wave
from pathlib import Path

from whisper_wayland.audio_conditioning.ffmpeg_tools import (
    _parse_silence_ranges,
    _speech_from_silence_ranges,
)
from whisper_wayland.audio_conditioning.fixtures import load_fixture_json
from whisper_wayland.audio_conditioning.harness import AudioConditioningHarness
from whisper_wayland.audio_conditioning.stream_replay import (
    StreamReplayHarness,
    _merged_interval_duration,
)

MIN_EXPECTED_STREAM_CHUNKS = 2
EXPECTED_MERGED_INTERVAL_DURATION = 20.0


def test_fixture_json_loads_relative_source(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "clean-001"
    fixture_dir.mkdir()
    source = fixture_dir / "source.wav"
    source.write_bytes(b"not real wav")
    (fixture_dir / "fixture.json").write_text(
        json.dumps(
            {
                "id": "clean-001",
                "sourceFile": "source.wav",
                "acousticProfile": "clean",
                "scenario": "Clean indoor speech",
                "expectedWords": ["hello"],
                "expectedSpeechWindows": [{"startSeconds": 0.5, "endSeconds": 1.5}],
                "noiseNotes": "quiet room",
            }
        )
    )

    fixture = load_fixture_json(fixture_dir / "fixture.json")

    assert fixture.fixture_id == "clean-001"
    assert fixture.source_path == source
    assert fixture.acoustic_profile == "clean"
    assert fixture.expected_words == ["hello"]


def test_speech_segments_are_inverse_of_silence() -> None:
    stderr = """
    [silencedetect @ 0xabc] silence_start: 0
    [silencedetect @ 0xabc] silence_end: 1.2 | silence_duration: 1.2
    [silencedetect @ 0xabc] silence_start: 2.8
    [silencedetect @ 0xabc] silence_end: 4.0 | silence_duration: 1.2
    """

    silence_ranges = _parse_silence_ranges(stderr, 5.0)
    speech_ranges = _speech_from_silence_ranges(silence_ranges, 5.0)

    assert silence_ranges == [(0.0, 1.2), (2.8, 4.0)]
    assert speech_ranges == [(1.2, 2.8), (4.0, 5.0)]


def test_harness_writes_local_report_for_synthetic_fixture(tmp_path: Path) -> None:
    fixture_dir = tmp_path / "fixture"
    fixture_dir.mkdir()
    source = fixture_dir / "source.wav"
    _write_synthetic_wav(source)
    (fixture_dir / "fixture.json").write_text(
        json.dumps(
            {
                "id": "synthetic-clean",
                "sourceFile": "source.wav",
                "acousticProfile": "clean",
                "scenario": "Synthetic tone with silence",
                "expectedWords": [],
            }
        )
    )
    output_root = tmp_path / "local" / "audio-conditioning"
    harness = AudioConditioningHarness(output_root=output_root, run_id="test-run")

    results = harness.run_paths([fixture_dir])

    assert len(results) == 1
    assert (output_root / "runs" / "test-run" / "run.json").exists()
    assert (output_root / "runs" / "test-run" / "report.md").exists()
    run_payload = json.loads((output_root / "runs" / "test-run" / "run.json").read_text())
    assert run_payload["schema"] == "whisper_wayland.audio_conditioning.run.v1"
    assert run_payload["summary"]["fixtureCount"] == 1


def test_stream_replay_writes_events_and_report(tmp_path: Path) -> None:
    source = tmp_path / "source.wav"
    _write_synthetic_wav(source)
    output_root = tmp_path / "local" / "audio-conditioning"
    harness = StreamReplayHarness(
        source_path=source,
        output_root=output_root,
        run_id="stream-test",
        chunk_seconds=0.6,
        overlap_seconds=0.1,
        profile_name="clean",
    )

    payload = harness.run()

    run_dir = output_root / "runs" / "stream-test"
    assert payload["schema"] == "whisper_wayland.audio_conditioning.stream_replay_run.v1"
    assert payload["summary"]["chunkCount"] >= MIN_EXPECTED_STREAM_CHUNKS
    assert (run_dir / "events.jsonl").exists()
    assert (run_dir / "run.json").exists()
    assert (run_dir / "report.md").exists()
    events = (run_dir / "events.jsonl").read_text().splitlines()
    assert any('"eventName": "chunk.received"' in event for event in events)
    assert any('"eventName": "run.completed"' in event for event in events)


def test_merged_interval_duration_counts_overlap_once() -> None:
    duration = _merged_interval_duration([(0.0, 10.0), (8.0, 15.0), (20.0, 25.0)])

    assert duration == EXPECTED_MERGED_INTERVAL_DURATION


def _write_synthetic_wav(path: Path) -> None:
    sample_rate = 16000
    silence = b"\x00\x00" * int(sample_rate * 0.4)
    tone_frame = (3000).to_bytes(2, byteorder="little", signed=True)
    tone = tone_frame * int(sample_rate * 0.6)
    frames = silence + tone + silence
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(frames)
