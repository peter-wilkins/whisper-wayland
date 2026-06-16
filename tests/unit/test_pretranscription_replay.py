"""Tests for pre-transcription replay harness."""

from __future__ import annotations

import whisper_wayland as ww
from whisper_wayland.pretranscription_replay import PretranscriptionReplay, ReplaySettings
from whisper_wayland.silero_vad import VadAudioChunk, VadSegment, VadSplitResult

EXPECTED_CHUNK_COUNT = 2


class FakeSileroVad:
    """Fake VAD splitter for replay tests."""

    def split_audio(
        self,
        audio_data: bytes,
        filename: str | None = None,
        **kwargs: object,
    ) -> VadSplitResult:
        """Return deterministic chunks."""
        return VadSplitResult(
            raw_duration_seconds=12.0,
            chunks=[
                VadAudioChunk(
                    segment=VadSegment(start_seconds=0.5, end_seconds=2.0),
                    audio_data=b"chunk-one",
                    content_type="audio/ogg",
                    filename_suffix=".chunk-0001.ogg",
                ),
                VadAudioChunk(
                    segment=VadSegment(start_seconds=4.0, end_seconds=6.0),
                    audio_data=b"chunk-two",
                    content_type="audio/ogg",
                    filename_suffix=".chunk-0002.ogg",
                ),
            ],
            threshold=0.5,
            model_path="fake.onnx",
        )


class FakeTranscriptionClient:
    """Fake client that transcribes from chunk bytes."""

    def __init__(self) -> None:
        """Create fake client."""
        self.last_transcription_backend = ww.TranscriptionBackendMetadata(
            provider="fake",
            processor_id="fake-model",
        )

    def transcribe_audio(self, audio_data: bytes) -> str:
        """Return deterministic text for each chunk."""
        if audio_data == b"chunk-one":
            return "First chunk."
        if audio_data == b"chunk-two":
            return "Second chunk."
        return ""


def test_pretranscription_replay_dry_run_writes_chunk_audio(tmp_path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"audio")
    replay = PretranscriptionReplay(
        settings=ReplaySettings(
            output_root=tmp_path / "runs",
            run_id="test-run",
        ),
        silero_vad=FakeSileroVad(),  # type: ignore[arg-type]
    )

    result = replay.run_file(source)

    assert result.chunk_count == EXPECTED_CHUNK_COUNT
    assert result.coalescing == {
        "minDurationSeconds": 4.0,
        "maxDurationSeconds": 12.0,
        "maxGapSeconds": 3.0,
    }
    assert result.assembled_text is None
    assert (replay.run_dir / "chunks/chunk-0001.ogg").read_bytes() == b"chunk-one"
    assert (replay.run_dir / "run.json").exists()
    assert (replay.run_dir / "report.md").exists()


def test_pretranscription_replay_transcribes_and_assembles_by_timeline(tmp_path) -> None:
    source = tmp_path / "source.wav"
    source.write_bytes(b"audio")
    replay = PretranscriptionReplay(
        settings=ReplaySettings(
            output_root=tmp_path / "runs",
            run_id="test-run",
        ),
        silero_vad=FakeSileroVad(),  # type: ignore[arg-type]
        client_factory=FakeTranscriptionClient,  # type: ignore[arg-type]
    )

    result = replay.run_file(source, transcribe=True)

    assert result.assembled_text == "First chunk. Second chunk."
    assert [chunk.text for chunk in result.chunks] == ["First chunk.", "Second chunk."]
    assert {chunk.transcription_provider for chunk in result.chunks} == {"fake"}
