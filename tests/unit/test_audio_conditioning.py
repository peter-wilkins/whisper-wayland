"""Tests for the local audio conditioning harness."""

from __future__ import annotations

import json
import math
import wave
from pathlib import Path

from whisper_wayland.audio_conditioning.ffmpeg_tools import (
    _parse_silence_ranges,
    _speech_from_silence_ranges,
)
from whisper_wayland.audio_conditioning.fixtures import load_fixture_json
from whisper_wayland.audio_conditioning.harness import AudioConditioningHarness
from whisper_wayland.audio_conditioning.models import SpeechSegment
from whisper_wayland.audio_conditioning.review_player import (
    _save_review_label,
    write_review_player,
)
from whisper_wayland.audio_conditioning.speech_ranking import rank_speech_segment
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
        transcription_candidate_limit=1,
        transcription_min_score=0.0,
    )

    payload = harness.run()

    run_dir = output_root / "runs" / "stream-test"
    assert payload["schema"] == "whisper_wayland.audio_conditioning.stream_replay_run.v1"
    assert payload["summary"]["chunkCount"] >= MIN_EXPECTED_STREAM_CHUNKS
    assert "averageSpeechScore" in payload["summary"]
    assert payload["topSpeechCandidates"]
    assert payload["transcriptionPlan"]["mode"] == "ranked_non_overlapping_candidates_dry_run"
    assert payload["transcriptionPlan"]["selectedSegmentCount"] == 1
    assert payload["transcriptionPlan"]["transcriptionEnabled"] is False
    assert payload["transcriptionPlan"]["segments"][0].speech_rank == 1
    assert payload["segments"][0].speech_rank is not None
    assert payload["segments"][0].speech_features["reason"]
    assert (run_dir / "events.jsonl").exists()
    assert (run_dir / "run.json").exists()
    assert (run_dir / "report.md").exists()
    events = (run_dir / "events.jsonl").read_text().splitlines()
    assert any('"eventName": "chunk.received"' in event for event in events)
    assert any('"eventName": "run.completed"' in event for event in events)


def test_merged_interval_duration_counts_overlap_once() -> None:
    duration = _merged_interval_duration([(0.0, 10.0), (8.0, 15.0), (20.0, 25.0)])

    assert duration == EXPECTED_MERGED_INTERVAL_DURATION


def test_speech_ranking_scores_tone_above_silence(tmp_path: Path) -> None:
    speechy = tmp_path / "speechy.wav"
    silent = tmp_path / "silent.wav"
    _write_sine_wav(speechy, frequency_hz=220.0, amplitude=1800, duration_seconds=2.0)
    _write_sine_wav(silent, frequency_hz=220.0, amplitude=0, duration_seconds=2.0)
    segment = SpeechSegment(index=1, start_seconds=0.0, end_seconds=2.0)

    speechy_ranking = rank_speech_segment(speechy, segment)
    silent_ranking = rank_speech_segment(silent, segment)

    assert speechy_ranking.score > silent_ranking.score
    assert speechy_ranking.reason == "weak_speech_candidate"
    assert silent_ranking.reason == "likely_silent"


def test_review_player_writes_audio_buttons_for_transcription_plan(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    segments_dir = run_dir / "segments"
    segments_dir.mkdir(parents=True)
    (segments_dir / "clip.ogg").write_bytes(b"fake ogg")
    (run_dir / "run.json").write_text(
        json.dumps(
            {
                "source": {"path": "source.m4a"},
                "transcriptionPlan": {
                    "selectedSegmentCount": 1,
                    "selectedDurationSeconds": 2.5,
                    "durationReductionPercent": 90.0,
                    "uploadSizeReductionPercent": 99.0,
                    "segments": [
                        {
                            "relative_path": "segments/clip.ogg",
                            "source_start_seconds": 1.0,
                            "source_end_seconds": 3.5,
                            "speech_rank": 1,
                            "speech_score": 0.91,
                            "speech_features": {"reason": "speech_candidate"},
                        }
                    ],
                },
            }
        )
    )

    index_path = write_review_player(run_dir)

    html = index_path.read_text()
    assert "WhisperWayland Audio Review" in html
    assert 'src="segments/clip.ogg"' in html
    assert "Score 0.910" in html
    assert "data-target=\"clip-1\"" in html
    assert 'data-label="speech"' in html
    assert 'data-label="partial"' in html
    assert 'data-label="noise"' in html


def test_review_player_saves_one_label_per_clip(tmp_path: Path) -> None:
    first_payload = {
        "relativePath": "segments/clip.ogg",
        "label": "noise",
        "speechRank": 1,
        "speechScore": 0.91,
        "sourceStartSeconds": 1.0,
        "sourceEndSeconds": 3.5,
    }
    second_payload = {**first_payload, "label": "partial"}

    _save_review_label(tmp_path, first_payload)
    labels_payload = _save_review_label(tmp_path, second_payload)

    labels = labels_payload["labels"]
    assert len(labels) == 1
    assert labels[0]["relativePath"] == "segments/clip.ogg"
    assert labels[0]["label"] == "partial"
    assert (tmp_path / "review-labels.json").exists()


def _write_synthetic_wav(path: Path) -> None:
    sample_rate = 16000
    silence = b"\x00\x00" * int(sample_rate * 0.4)
    tone = bytearray()
    for index in range(int(sample_rate * 0.6)):
        value = int(3000 * math.sin(2 * math.pi * 220 * index / sample_rate))
        tone.extend(value.to_bytes(2, byteorder="little", signed=True))
    frames = silence + tone + silence
    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))


def _write_sine_wav(
    path: Path,
    *,
    frequency_hz: float,
    amplitude: int,
    duration_seconds: float,
) -> None:
    sample_rate = 16000
    frame_count = int(sample_rate * duration_seconds)
    frames = bytearray()
    for index in range(frame_count):
        value = int(amplitude * math.sin(2 * math.pi * frequency_hz * index / sample_rate))
        frames.extend(value.to_bytes(2, byteorder="little", signed=True))

    with wave.open(str(path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(frames))
