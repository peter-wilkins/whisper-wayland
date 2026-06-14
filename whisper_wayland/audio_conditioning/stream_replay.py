"""Pseudo-streaming replay harness for local audio-conditioning experiments."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
import typing
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from whisper_wayland.audio_conditioning.ffmpeg_tools import (
    detect_speech_segments,
    highpass_to_wav,
    probe_duration_seconds,
)
from whisper_wayland.audio_conditioning.harness import DEFAULT_LOCAL_ROOT
from whisper_wayland.audio_conditioning.profiles import profile_for_name
from whisper_wayland.audio_conditioning.speech_ranking import rank_speech_segment

DEFAULT_CHUNK_SECONDS = 10.0
DEFAULT_OVERLAP_SECONDS = 1.0
DEFAULT_PROFILE = "outdoorwind"
DEFAULT_OPUS_BITRATE = "18k"
EVENT_SCHEMA = "whisper_wayland.audio_conditioning.stream_event.v1"
RUN_SCHEMA = "whisper_wayland.audio_conditioning.stream_replay_run.v1"


@dataclass(frozen=True)
class ReplayChunk:
    """One replayed source interval."""

    index: int
    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        """Chunk duration in seconds."""
        return round(max(0.0, self.end_seconds - self.start_seconds), 3)


@dataclass(frozen=True)
class KeptSegment:
    """One encoded segment kept by the stream replay."""

    chunk_index: int
    source_start_seconds: float
    source_end_seconds: float
    relative_path: str
    byte_length: int
    decision: str
    speech_rank: int | None
    speech_score: float
    speech_features: dict[str, float | str]

    @property
    def duration_seconds(self) -> float:
        """Kept duration in seconds."""
        return round(max(0.0, self.source_end_seconds - self.source_start_seconds), 3)


class StreamReplayHarness:
    """Replay an audio file as bounded chunks and emit local experiment metrics."""

    def __init__(  # noqa: PLR0913
        self,
        source_path: Path,
        output_root: Path = DEFAULT_LOCAL_ROOT,
        run_id: str | None = None,
        chunk_seconds: float = DEFAULT_CHUNK_SECONDS,
        overlap_seconds: float = DEFAULT_OVERLAP_SECONDS,
        profile_name: str = DEFAULT_PROFILE,
        opus_bitrate: str = DEFAULT_OPUS_BITRATE,
    ) -> None:
        """Create a pseudo-streaming replay run."""
        self.source_path = source_path.expanduser()
        self.output_root = output_root
        self.run_id = run_id or _utc_run_id()
        self.chunk_seconds = chunk_seconds
        self.overlap_seconds = overlap_seconds
        self.profile = profile_for_name(profile_name)
        self.opus_bitrate = opus_bitrate
        self.run_dir = output_root / "runs" / self.run_id
        self.segments_dir = self.run_dir / "segments"
        self.manifests_dir = self.run_dir / "manifests"
        self.events_path = self.run_dir / "events.jsonl"

    def run(self) -> dict[str, typing.Any]:
        """Run replay, write events/report/run JSON, and return run payload."""
        self.segments_dir.mkdir(parents=True, exist_ok=True)
        self.manifests_dir.mkdir(parents=True, exist_ok=True)

        start_monotonic = time.monotonic()
        source_duration = probe_duration_seconds(self.source_path)
        source_bytes = self.source_path.stat().st_size
        chunks = self._chunks(source_duration)
        self._write_event(
            "run.started",
            {
                "sourcePath": str(self.source_path),
                "sourceDurationSeconds": source_duration,
                "sourceByteLength": source_bytes,
                "chunkSeconds": self.chunk_seconds,
                "overlapSeconds": self.overlap_seconds,
                "profile": asdict(self.profile),
            },
            start_monotonic,
        )

        kept_segments: list[KeptSegment] = []
        for chunk in chunks:
            self._write_event("chunk.received", asdict(chunk), start_monotonic)
            kept_segments.extend(self._process_chunk(chunk, start_monotonic))

        kept_segments = _assign_speech_ranks(kept_segments)
        elapsed = round(time.monotonic() - start_monotonic, 3)
        payload = self._run_payload(
            source_duration=source_duration,
            source_bytes=source_bytes,
            chunks=chunks,
            kept_segments=kept_segments,
            elapsed_seconds=elapsed,
        )
        self._write_json(self.run_dir / "run.json", payload)
        self._write_report(self.run_dir / "report.md", payload)
        self._write_event("run.completed", payload["summary"], start_monotonic)
        return payload

    def _process_chunk(
        self,
        chunk: ReplayChunk,
        run_start_monotonic: float,
    ) -> list[KeptSegment]:
        with tempfile.TemporaryDirectory(prefix="ww-stream-replay-") as tmp_dir_text:
            tmp_dir = Path(tmp_dir_text)
            source_chunk = tmp_dir / "source.wav"
            conditioned_chunk = tmp_dir / "conditioned.wav"
            self._extract_chunk_to_wav(chunk, source_chunk)
            highpass_to_wav(source_chunk, conditioned_chunk, self.profile)
            speech_segments = detect_speech_segments(
                conditioned_chunk,
                chunk.duration_seconds,
                self.profile,
            )
            if not speech_segments:
                self._write_event(
                    "chunk.discarded",
                    {
                        **asdict(chunk),
                        "decision": "discarded_no_speech",
                    },
                    run_start_monotonic,
                )
                return []

            kept: list[KeptSegment] = []
            for segment in speech_segments:
                source_start = round(chunk.start_seconds + segment.start_seconds, 3)
                source_end = round(chunk.start_seconds + segment.end_seconds, 3)
                ranking = rank_speech_segment(conditioned_chunk, segment)
                output_path = (
                    self.segments_dir
                    / f"chunk-{chunk.index:04d}-{source_start:.3f}-{source_end:.3f}.ogg"
                )
                self._encode_opus_segment(
                    conditioned_chunk,
                    output_path,
                    segment.start_seconds,
                    segment.duration_seconds,
                )
                kept_segment = KeptSegment(
                    chunk_index=chunk.index,
                    source_start_seconds=source_start,
                    source_end_seconds=source_end,
                    relative_path=output_path.relative_to(self.run_dir).as_posix(),
                    byte_length=output_path.stat().st_size,
                    decision="kept_speech_like_audio",
                    speech_rank=None,
                    speech_score=ranking.score,
                    speech_features=ranking.to_json(),
                )
                kept.append(kept_segment)
                self._write_event(
                    "segment.kept",
                    asdict(kept_segment),
                    run_start_monotonic,
                )
            return kept

    def _chunks(self, duration_seconds: float) -> list[ReplayChunk]:
        chunks: list[ReplayChunk] = []
        start = 0.0
        step = max(0.001, self.chunk_seconds - self.overlap_seconds)
        index = 1
        while start < duration_seconds:
            end = min(duration_seconds, start + self.chunk_seconds)
            chunks.append(
                ReplayChunk(
                    index=index,
                    start_seconds=round(start, 3),
                    end_seconds=round(end, 3),
                )
            )
            if end >= duration_seconds:
                break
            start += step
            index += 1
        return chunks

    def _extract_chunk_to_wav(self, chunk: ReplayChunk, output_path: Path) -> None:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-ss",
                f"{chunk.start_seconds:.3f}",
                "-t",
                f"{chunk.duration_seconds:.3f}",
                "-i",
                str(self.source_path),
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                str(output_path),
            ]
        )

    def _encode_opus_segment(
        self,
        wav_path: Path,
        output_path: Path,
        start_seconds: float,
        duration_seconds: float,
    ) -> None:
        _run_ffmpeg(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-ss",
                f"{start_seconds:.3f}",
                "-t",
                f"{duration_seconds:.3f}",
                "-i",
                str(wav_path),
                "-c:a",
                "libopus",
                "-b:a",
                self.opus_bitrate,
                "-vbr",
                "on",
                str(output_path),
            ]
        )

    def _run_payload(
        self,
        source_duration: float,
        source_bytes: int,
        chunks: list[ReplayChunk],
        kept_segments: list[KeptSegment],
        elapsed_seconds: float,
    ) -> dict[str, typing.Any]:
        audio_sent_duration = round(
            sum(segment.duration_seconds for segment in kept_segments),
            3,
        )
        kept_source_duration = _merged_interval_duration(
            [
                (segment.source_start_seconds, segment.source_end_seconds)
                for segment in kept_segments
            ]
        )
        encoded_bytes = sum(segment.byte_length for segment in kept_segments)
        top_segments = _top_speech_candidates(kept_segments)
        return {
            "schema": RUN_SCHEMA,
            "runId": self.run_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "source": {
                "path": str(self.source_path),
                "durationSeconds": source_duration,
                "byteLength": source_bytes,
            },
            "pipeline": {
                "mode": "pseudo_streaming_replay",
                "chunkSeconds": self.chunk_seconds,
                "overlapSeconds": self.overlap_seconds,
                "profile": asdict(self.profile),
                "opusBitrate": self.opus_bitrate,
                "transcriptionEnabled": False,
            },
            "summary": {
                "chunkCount": len(chunks),
                "keptSegmentCount": len(kept_segments),
                "topSpeechCandidateCount": len(top_segments),
                "averageSpeechScore": _average_speech_score(kept_segments),
                "rawDurationSeconds": source_duration,
                "keptDurationSeconds": audio_sent_duration,
                "audioDurationSentSeconds": audio_sent_duration,
                "keptSourceCoverageSeconds": kept_source_duration,
                "discardedSourceCoverageSeconds": round(
                    max(0.0, source_duration - kept_source_duration),
                    3,
                ),
                "rawByteLength": source_bytes,
                "encodedByteLength": encoded_bytes,
                "uploadSizeReductionPercent": _size_reduction_percent(
                    source_bytes,
                    encoded_bytes,
                ),
                "processingElapsedSeconds": elapsed_seconds,
            },
            "segments": kept_segments,
            "topSpeechCandidates": top_segments,
        }

    def _write_event(
        self,
        event_name: str,
        payload: dict[str, typing.Any],
        run_start_monotonic: float,
    ) -> None:
        event = {
            "schema": EVENT_SCHEMA,
            "eventName": event_name,
            "runId": self.run_id,
            "at": datetime.now(timezone.utc).isoformat(),
            "elapsedSeconds": round(time.monotonic() - run_start_monotonic, 3),
            "payload": payload,
        }
        with self.events_path.open("a") as handle:
            handle.write(json.dumps(event, default=_json_default) + "\n")

    @staticmethod
    def _write_json(path: Path, payload: dict[str, typing.Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n")

    @staticmethod
    def _write_report(path: Path, payload: dict[str, typing.Any]) -> None:
        summary = payload["summary"]
        lines = [
            f"# Stream Replay Run {payload['runId']}",
            "",
            f"- Source: `{payload['source']['path']}`",
            f"- Raw duration: {summary['rawDurationSeconds']:.3f}s",
            f"- Chunks: {summary['chunkCount']}",
            f"- Kept segments: {summary['keptSegmentCount']}",
            f"- Top speech candidates: {summary['topSpeechCandidateCount']}",
            f"- Average speech score: {summary['averageSpeechScore']:.3f}",
            f"- Audio duration sent: {summary['audioDurationSentSeconds']:.3f}s",
            f"- Source coverage kept/discarded: "
            f"{summary['keptSourceCoverageSeconds']:.3f}s / "
            f"{summary['discardedSourceCoverageSeconds']:.3f}s",
            f"- Raw/encoded bytes: {summary['rawByteLength']} / "
            f"{summary['encodedByteLength']}",
            f"- Upload size reduction: {summary['uploadSizeReductionPercent']:.1f}%",
            f"- Processing elapsed: {summary['processingElapsedSeconds']:.3f}s",
            "- Transcription: disabled",
            "",
            "## Segments",
            "",
            "| Rank | Score | Chunk | Start | End | Duration | Bytes | Reason | File |",
            "| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
        for segment in payload["segments"]:
            duration = segment.duration_seconds
            lines.append(
                f"| {_rank_cell(segment.speech_rank)} | "
                f"{segment.speech_score:.3f} | "
                f"{segment.chunk_index} | "
                f"{segment.source_start_seconds:.3f} | "
                f"{segment.source_end_seconds:.3f} | "
                f"{duration:.3f} | "
                f"{segment.byte_length} | "
                f"{segment.speech_features['reason']} | "
                f"`{segment.relative_path}` |"
            )
        path.write_text("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    """Run a pseudo-streaming replay over one audio file."""
    parser = argparse.ArgumentParser(
        description="Replay a local audio file in chunks and emit stream metrics.",
    )
    parser.add_argument("audio_file", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_LOCAL_ROOT)
    parser.add_argument("--run-id")
    parser.add_argument("--chunk-seconds", type=float, default=DEFAULT_CHUNK_SECONDS)
    parser.add_argument("--overlap-seconds", type=float, default=DEFAULT_OVERLAP_SECONDS)
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--opus-bitrate", default=DEFAULT_OPUS_BITRATE)
    args = parser.parse_args(argv)

    harness = StreamReplayHarness(
        source_path=args.audio_file,
        output_root=args.output_root,
        run_id=args.run_id,
        chunk_seconds=args.chunk_seconds,
        overlap_seconds=args.overlap_seconds,
        profile_name=args.profile,
        opus_bitrate=args.opus_bitrate,
    )
    payload = harness.run()
    print(f"Wrote run: {harness.run_dir}")
    print(f"Chunks: {payload['summary']['chunkCount']}")
    print(f"Kept segments: {payload['summary']['keptSegmentCount']}")
    print(f"Audio duration sent: {payload['summary']['audioDurationSentSeconds']}s")
    return 0


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(  # noqa: S603 - fixed executable args, no shell
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())


def _size_reduction_percent(original_size: int, new_size: int) -> float:
    if original_size <= 0:
        return 0.0
    return round((1 - (new_size / original_size)) * 100, 1)


def _merged_interval_duration(intervals: list[tuple[float, float]]) -> float:
    if not intervals:
        return 0.0

    sorted_intervals = sorted(intervals)
    merged: list[tuple[float, float]] = []
    for start, end in sorted_intervals:
        if not merged or start > merged[-1][1]:
            merged.append((start, end))
            continue
        previous_start, previous_end = merged[-1]
        merged[-1] = (previous_start, max(previous_end, end))
    return round(sum(end - start for start, end in merged), 3)


def _assign_speech_ranks(segments: list[KeptSegment]) -> list[KeptSegment]:
    ranked_segments = sorted(
        segments,
        key=lambda segment: (
            -segment.speech_score,
            segment.source_start_seconds,
            segment.source_end_seconds,
        ),
    )
    rank_by_identity = {
        id(segment): rank for rank, segment in enumerate(ranked_segments, start=1)
    }
    return [
        KeptSegment(
            chunk_index=segment.chunk_index,
            source_start_seconds=segment.source_start_seconds,
            source_end_seconds=segment.source_end_seconds,
            relative_path=segment.relative_path,
            byte_length=segment.byte_length,
            decision=segment.decision,
            speech_rank=rank_by_identity[id(segment)],
            speech_score=segment.speech_score,
            speech_features=segment.speech_features,
        )
        for segment in segments
    ]


def _top_speech_candidates(segments: list[KeptSegment]) -> list[KeptSegment]:
    return sorted(
        segments,
        key=lambda segment: (
            segment.speech_rank is None,
            segment.speech_rank or len(segments) + 1,
        ),
    )[:10]


def _average_speech_score(segments: list[KeptSegment]) -> float:
    if not segments:
        return 0.0
    return round(sum(segment.speech_score for segment in segments) / len(segments), 3)


def _rank_cell(rank: int | None) -> str:
    return "" if rank is None else str(rank)


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _json_default(value: typing.Any) -> typing.Any:
    if isinstance(value, Path):
        return str(value)
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


if __name__ == "__main__":
    raise SystemExit(main())
