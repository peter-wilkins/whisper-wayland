"""Replay harness for pre-transcription chunking experiments."""

from __future__ import annotations

import argparse
import json
import logging
import typing
from concurrent import futures
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import whisper_wayland as ww
from whisper_wayland.silero_vad import (
    SileroVadPreprocessor,
    VadAudioChunk,
)

_logger = logging.getLogger(__name__)

DEFAULT_OUTPUT_ROOT = Path("local/pretranscription-replay")
DEFAULT_MAX_IN_FLIGHT_CHUNKS = 16
DEFAULT_COALESCE_MIN_DURATION_SECONDS = 4.0
DEFAULT_COALESCE_MAX_DURATION_SECONDS = 12.0
DEFAULT_COALESCE_MAX_GAP_SECONDS = 3.0
SCHEMA = "whisper-wayland.pretranscription-replay.v1"


@dataclass(frozen=True)
class ReplaySettings:
    """Settings for a pre-transcription replay run."""

    output_root: Path = DEFAULT_OUTPUT_ROOT
    run_id: str | None = None
    max_in_flight_chunks: int = DEFAULT_MAX_IN_FLIGHT_CHUNKS
    coalesce_min_duration_seconds: float = DEFAULT_COALESCE_MIN_DURATION_SECONDS
    coalesce_max_duration_seconds: float = DEFAULT_COALESCE_MAX_DURATION_SECONDS
    coalesce_max_gap_seconds: float = DEFAULT_COALESCE_MAX_GAP_SECONDS
    chunk_whisper_model: str | None = None
    chunk_race_models: list[str] | None = None


@dataclass(frozen=True)
class ReplayChunkResult:
    """Replay result for one timeline chunk."""

    index: int
    start_seconds: float
    end_seconds: float
    duration_seconds: float
    audio_relative_path: str
    byte_length: int
    text: str | None
    transcription_provider: str | None
    transcription_processor_id: str | None
    error: str | None


@dataclass(frozen=True)
class ReplayResult:
    """Replay run result."""

    schema: str
    source_path: str
    run_dir: str
    raw_duration_seconds: float
    chunk_count: int
    transcribe_enabled: bool
    coalescing: dict[str, float]
    chunk_transcription: dict[str, object] | None
    assembled_text: str | None
    chunks: list[ReplayChunkResult]


@dataclass(frozen=True)
class ChunkTranscriptionConfig:
    """Config proxy that overrides only chunk transcription provider settings."""

    base_config: typing.Any
    whisper_model: str
    transcription_race_models: list[str]

    def __getattr__(self, name: str) -> object:
        """Delegate all other configuration to the base config."""
        return getattr(self.base_config, name)


class PretranscriptionReplay:
    """Run pre-transcription chunk detection and optional chunk transcription."""

    def __init__(
        self,
        *,
        settings: ReplaySettings | None = None,
        silero_vad: SileroVadPreprocessor | None = None,
        client_factory: typing.Callable[[], ww.TranscriptionClient] | None = None,
    ) -> None:
        """Create a replay harness."""
        self.settings = settings or ReplaySettings()
        self.output_root = self.settings.output_root
        self.run_id = self.settings.run_id or _utc_run_id()
        self.run_dir = self.output_root / "runs" / self.run_id
        self.chunks_dir = self.run_dir / "chunks"
        self.silero_vad = silero_vad or SileroVadPreprocessor()
        self.client_factory = client_factory
        self.max_in_flight_chunks = max(1, self.settings.max_in_flight_chunks)
        self.coalesce_min_duration_seconds = max(
            0.0,
            self.settings.coalesce_min_duration_seconds,
        )
        self.coalesce_max_duration_seconds = max(
            0.0,
            self.settings.coalesce_max_duration_seconds,
        )
        self.coalesce_max_gap_seconds = max(0.0, self.settings.coalesce_max_gap_seconds)

    def run_file(self, source_path: Path, *, transcribe: bool = False) -> ReplayResult:
        """Run replay for a local source file."""
        self.chunks_dir.mkdir(parents=True, exist_ok=True)
        audio_data = source_path.read_bytes()
        split_result = self.silero_vad.split_audio(
            audio_data,
            source_path.name,
            min_chunk_duration_seconds=self.coalesce_min_duration_seconds,
            max_chunk_duration_seconds=self.coalesce_max_duration_seconds,
            max_chunk_gap_seconds=self.coalesce_max_gap_seconds,
        )
        chunk_results = self._write_chunk_audio(split_result.chunks)
        chunk_transcription = None
        if transcribe:
            chunk_config = self._chunk_transcription_config()
            chunk_transcription = {
                "model": chunk_config.whisper_model,
                "raceModels": chunk_config.transcription_race_models,
            }
            chunk_results = self._transcribe_chunks(chunk_results, chunk_config)

        assembled_text = _assemble_text(chunk_results) if transcribe else None
        result = ReplayResult(
            schema=SCHEMA,
            source_path=str(source_path),
            run_dir=str(self.run_dir),
            raw_duration_seconds=split_result.raw_duration_seconds,
            chunk_count=len(chunk_results),
            transcribe_enabled=transcribe,
            coalescing={
                "minDurationSeconds": self.coalesce_min_duration_seconds,
                "maxDurationSeconds": self.coalesce_max_duration_seconds,
                "maxGapSeconds": self.coalesce_max_gap_seconds,
            },
            chunk_transcription=chunk_transcription,
            assembled_text=assembled_text,
            chunks=chunk_results,
        )
        self._write_result(result)
        return result

    def _write_chunk_audio(self, chunks: list[VadAudioChunk]) -> list[ReplayChunkResult]:
        results = []
        for index, chunk in enumerate(chunks, start=1):
            chunk_path = self.chunks_dir / f"chunk-{index:04d}.ogg"
            chunk_path.write_bytes(chunk.audio_data)
            results.append(
                ReplayChunkResult(
                    index=index,
                    start_seconds=chunk.segment.start_seconds,
                    end_seconds=chunk.segment.end_seconds,
                    duration_seconds=chunk.segment.duration_seconds,
                    audio_relative_path=chunk_path.relative_to(self.run_dir).as_posix(),
                    byte_length=len(chunk.audio_data),
                    text=None,
                    transcription_provider=None,
                    transcription_processor_id=None,
                    error=None,
                )
            )
        return results

    def _transcribe_chunks(
        self,
        chunk_results: list[ReplayChunkResult],
        chunk_config: ChunkTranscriptionConfig,
    ) -> list[ReplayChunkResult]:
        if not chunk_results:
            return []

        completed: dict[int, ReplayChunkResult] = {}
        with futures.ThreadPoolExecutor(max_workers=self.max_in_flight_chunks) as executor:
            future_to_chunk = {
                executor.submit(self._transcribe_chunk, chunk, chunk_config): chunk
                for chunk in chunk_results
            }
            for completed_future in futures.as_completed(future_to_chunk):
                chunk = future_to_chunk[completed_future]
                try:
                    completed[chunk.index] = completed_future.result()
                except Exception as e:
                    _logger.warning("Chunk %s transcription failed: %s", chunk.index, e)
                    completed[chunk.index] = _replace_chunk(
                        chunk,
                        text=None,
                        transcription_provider=None,
                        transcription_processor_id=None,
                        error=str(e),
                    )

        return [completed[chunk.index] for chunk in chunk_results]

    def _transcribe_chunk(
        self,
        chunk: ReplayChunkResult,
        chunk_config: ChunkTranscriptionConfig,
    ) -> ReplayChunkResult:
        client = self._new_transcription_client(chunk_config)
        audio_path = self.run_dir / chunk.audio_relative_path
        text = client.transcribe_audio(audio_path.read_bytes()) or ""
        backend = client.last_transcription_backend
        return _replace_chunk(
            chunk,
            text=text,
            transcription_provider=backend.provider if backend else None,
            transcription_processor_id=backend.processor_id if backend else None,
            error=None,
        )

    def _new_transcription_client(
        self,
        chunk_config: ChunkTranscriptionConfig,
    ) -> ww.TranscriptionClient:
        if self.client_factory:
            return self.client_factory()
        return ww.TranscriptionClient(chunk_config)  # type: ignore[arg-type]

    def _chunk_transcription_config(self) -> ChunkTranscriptionConfig:
        base_config = ww.Config()
        return ChunkTranscriptionConfig(
            base_config=base_config,
            whisper_model=(
                self.settings.chunk_whisper_model
                or base_config.pretranscription_chunk_whisper_model
            ),
            transcription_race_models=(
                self.settings.chunk_race_models
                if self.settings.chunk_race_models is not None
                else base_config.pretranscription_chunk_race_models
            ),
        )

    def _write_result(self, result: ReplayResult) -> None:
        payload = asdict(result)
        (self.run_dir / "run.json").write_text(
            json.dumps(payload, indent=2) + "\n",
            encoding="utf-8",
        )
        _write_report(self.run_dir / "report.md", result)


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for pre-transcription replay."""
    parser = argparse.ArgumentParser(
        description="Replay pre-transcription chunk detection over local audio.",
    )
    parser.add_argument("audio_file", type=Path)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--run-id")
    parser.add_argument(
        "--transcribe",
        action="store_true",
        help="Spend API calls to transcribe detected chunks.",
    )
    parser.add_argument(
        "--max-in-flight-chunks",
        type=int,
        default=DEFAULT_MAX_IN_FLIGHT_CHUNKS,
        help="Safety ceiling for parallel chunk transcription jobs.",
    )
    parser.add_argument(
        "--coalesce-min-duration-seconds",
        type=float,
        default=DEFAULT_COALESCE_MIN_DURATION_SECONDS,
        help="Merge adjacent VAD chunks until phrase chunks are at least this long.",
    )
    parser.add_argument(
        "--coalesce-max-duration-seconds",
        type=float,
        default=DEFAULT_COALESCE_MAX_DURATION_SECONDS,
        help="Do not merge phrase chunks beyond this duration.",
    )
    parser.add_argument(
        "--coalesce-max-gap-seconds",
        type=float,
        default=DEFAULT_COALESCE_MAX_GAP_SECONDS,
        help="Maximum silence gap between VAD chunks that can be merged.",
    )
    parser.add_argument(
        "--chunk-whisper-model",
        help=(
            "Override PRETRANSCRIPTION_CHUNK_WHISPER_MODEL for this replay "
            "without changing normal batch transcription."
        ),
    )
    parser.add_argument(
        "--chunk-race-models",
        help=(
            "Comma-separated chunk-only race models. Empty string means no race. "
            "Defaults to PRETRANSCRIPTION_CHUNK_RACE_MODELS."
        ),
    )
    args = parser.parse_args(argv)

    replay = PretranscriptionReplay(
        settings=ReplaySettings(
            output_root=args.output_root,
            run_id=args.run_id,
            max_in_flight_chunks=args.max_in_flight_chunks,
            coalesce_min_duration_seconds=args.coalesce_min_duration_seconds,
            coalesce_max_duration_seconds=args.coalesce_max_duration_seconds,
            coalesce_max_gap_seconds=args.coalesce_max_gap_seconds,
            chunk_whisper_model=args.chunk_whisper_model,
            chunk_race_models=(
                _parse_csv(args.chunk_race_models)
                if args.chunk_race_models is not None
                else None
            ),
        ),
    )
    result = replay.run_file(args.audio_file, transcribe=args.transcribe)
    print(f"Wrote run: {result.run_dir}")
    print(f"Duration: {result.raw_duration_seconds:.3f}s")
    print(f"Chunks: {result.chunk_count}")
    if result.assembled_text:
        print(result.assembled_text)
    return 0


def _replace_chunk(
    chunk: ReplayChunkResult,
    *,
    text: str | None,
    transcription_provider: str | None,
    transcription_processor_id: str | None,
    error: str | None,
) -> ReplayChunkResult:
    return ReplayChunkResult(
        index=chunk.index,
        start_seconds=chunk.start_seconds,
        end_seconds=chunk.end_seconds,
        duration_seconds=chunk.duration_seconds,
        audio_relative_path=chunk.audio_relative_path,
        byte_length=chunk.byte_length,
        text=text,
        transcription_provider=transcription_provider,
        transcription_processor_id=transcription_processor_id,
        error=error,
    )


def _assemble_text(chunks: list[ReplayChunkResult]) -> str:
    return " ".join(
        chunk.text.strip()
        for chunk in sorted(chunks, key=lambda item: item.start_seconds)
        if chunk.text and chunk.text.strip()
    )


def _write_report(path: Path, result: ReplayResult) -> None:
    lines = [
        f"# Pre-transcription Replay {Path(result.run_dir).name}",
        "",
        f"- Source: `{result.source_path}`",
        f"- Duration: `{result.raw_duration_seconds:.3f}s`",
        f"- Chunks: `{result.chunk_count}`",
        f"- Transcribed: `{result.transcribe_enabled}`",
        f"- Coalesce min duration: `{result.coalescing['minDurationSeconds']:.3f}s`",
        f"- Coalesce max duration: `{result.coalescing['maxDurationSeconds']:.3f}s`",
        f"- Coalesce max gap: `{result.coalescing['maxGapSeconds']:.3f}s`",
    ]
    if result.chunk_transcription:
        lines.extend(
            [
                f"- Chunk model: `{result.chunk_transcription['model']}`",
                f"- Chunk race models: `{result.chunk_transcription['raceModels']}`",
            ]
        )
    if result.assembled_text:
        lines.extend(["", "## Assembled Text", "", result.assembled_text])
    lines.extend(["", "## Chunks", ""])
    for chunk in result.chunks:
        status = "error" if chunk.error else "ok"
        lines.append(
            f"- `{chunk.index:04d}` `{chunk.start_seconds:.3f}`-"
            f"`{chunk.end_seconds:.3f}` `{chunk.duration_seconds:.3f}s` `{status}`"
        )
        if chunk.text:
            lines.append(f"  - {chunk.text}")
        if chunk.error:
            lines.append(f"  - error: {chunk.error}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


if __name__ == "__main__":
    raise SystemExit(main())
