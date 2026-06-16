"""CPU-only Silero VAD preprocessing via ONNX Runtime."""

from __future__ import annotations

import io
import json
import logging
import subprocess
import tempfile
import urllib.request
import wave
from contextlib import suppress
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import onnxruntime as ort

_logger = logging.getLogger(__name__)

DEFAULT_MODEL_URL = (
    "https://github.com/snakers4/silero-vad/raw/master/src/silero_vad/data/"
    "silero_vad_op18_ifless.onnx"
)
DEFAULT_MODEL_PATH = Path("local/models/silero_vad_op18_ifless.onnx")
SAMPLE_RATE = 16000
WINDOW_SAMPLES = 512
CONTEXT_SAMPLES = 64
STATE_SHAPE = (2, 1, 128)


@dataclass(frozen=True)
class VadCoalescingConfig:
    """Settings for merging adjacent VAD speech regions into phrase chunks."""

    min_chunk_duration_seconds: float
    max_chunk_duration_seconds: float | None
    max_chunk_gap_seconds: float


@dataclass(frozen=True)
class VadSegment:
    """One detected speech segment."""

    start_seconds: float
    end_seconds: float

    @property
    def duration_seconds(self) -> float:
        """Segment duration."""
        return round(max(0.0, self.end_seconds - self.start_seconds), 3)


@dataclass(frozen=True)
class VadResult:
    """Audio and metadata after Silero VAD filtering."""

    audio_data: bytes
    content_type: str
    filename_suffix: str
    raw_duration_seconds: float
    speech_duration_seconds: float
    segments: list[VadSegment]
    threshold: float
    model_path: str

    def metadata(self) -> dict[str, object]:
        """Return JSON-friendly VAD metadata."""
        return {
            "enabled": True,
            "provider": "silero",
            "threshold": self.threshold,
            "modelPath": self.model_path,
            "rawDurationSeconds": self.raw_duration_seconds,
            "speechDurationSeconds": self.speech_duration_seconds,
            "durationReductionPercent": _duration_reduction_percent(
                self.raw_duration_seconds,
                self.speech_duration_seconds,
            ),
            "segmentCount": len(self.segments),
            "segments": [asdict(segment) for segment in self.segments],
        }


@dataclass(frozen=True)
class VadAudioChunk:
    """One detected speech chunk exported as audio bytes."""

    segment: VadSegment
    audio_data: bytes
    content_type: str
    filename_suffix: str


@dataclass(frozen=True)
class VadSplitResult:
    """Speech chunks and metadata after local VAD chunking."""

    raw_duration_seconds: float
    chunks: list[VadAudioChunk]
    threshold: float
    model_path: str


class SileroVadPreprocessor:
    """Preprocess audio by keeping only Silero VAD speech regions."""

    def __init__(
        self,
        *,
        model_path: Path = DEFAULT_MODEL_PATH,
        model_url: str = DEFAULT_MODEL_URL,
        threshold: float = 0.5,
    ) -> None:
        """Create the preprocessor."""
        self.model_path = model_path
        self.model_url = model_url
        self.threshold = threshold

    def filter_audio(self, audio_data: bytes, filename: str | None = None) -> VadResult:
        """Return speech-only Ogg audio for transcription."""
        split_result = self.split_audio(audio_data, filename)
        if not split_result.chunks:
            return VadResult(
                audio_data=b"",
                content_type="audio/ogg",
                filename_suffix=".silero.ogg",
                raw_duration_seconds=split_result.raw_duration_seconds,
                speech_duration_seconds=0.0,
                segments=[],
                threshold=split_result.threshold,
                model_path=split_result.model_path,
            )

        with tempfile.TemporaryDirectory(prefix="ww-silero-vad-") as tmp_text:
            tmp_dir = Path(tmp_text)
            speech_path = tmp_dir / "speech.ogg"
            concat_path = tmp_dir / "concat.txt"
            chunk_paths = []
            for index, chunk in enumerate(split_result.chunks, start=1):
                chunk_path = tmp_dir / f"chunk-{index:04d}.ogg"
                chunk_path.write_bytes(chunk.audio_data)
                chunk_paths.append(chunk_path)

            concat_path.write_text(
                "\n".join(f"file '{path.resolve()}'" for path in chunk_paths) + "\n",
                encoding="utf-8",
            )
            _run_ffmpeg(
                [
                    "ffmpeg",
                    "-hide_banner",
                    "-y",
                    "-f",
                    "concat",
                    "-safe",
                    "0",
                    "-i",
                    str(concat_path),
                    "-c",
                    "copy",
                    str(speech_path),
                ]
            )
            speech_duration = round(
                sum(chunk.segment.duration_seconds for chunk in split_result.chunks),
                3,
            )
            return VadResult(
                audio_data=speech_path.read_bytes(),
                content_type="audio/ogg",
                filename_suffix=".silero.ogg",
                raw_duration_seconds=split_result.raw_duration_seconds,
                speech_duration_seconds=speech_duration,
                segments=[chunk.segment for chunk in split_result.chunks],
                threshold=split_result.threshold,
                model_path=split_result.model_path,
            )

    def split_audio(
        self,
        audio_data: bytes,
        filename: str | None = None,
        *,
        min_chunk_duration_seconds: float = 0.0,
        max_chunk_duration_seconds: float | None = None,
        max_chunk_gap_seconds: float = 0.0,
    ) -> VadSplitResult:
        """Return individual speech chunks as Ogg audio for early transcription."""
        self._ensure_model()
        with tempfile.TemporaryDirectory(prefix="ww-silero-vad-") as tmp_text:
            tmp_dir = Path(tmp_text)
            source_path = tmp_dir / (filename or "input.audio")
            source_path.write_bytes(audio_data)
            wav_path = tmp_dir / "input.wav"

            _ffmpeg_to_wav(source_path, wav_path)
            probabilities = self._probabilities(wav_path)
            raw_duration = _wav_duration_seconds(wav_path)
            segments = _segments_from_probabilities(probabilities, self.threshold)
            segments = _coalesce_segments(
                segments,
                min_chunk_duration_seconds=min_chunk_duration_seconds,
                max_chunk_duration_seconds=max_chunk_duration_seconds,
                max_chunk_gap_seconds=max_chunk_gap_seconds,
            )
            if not segments:
                return VadSplitResult(
                    raw_duration_seconds=raw_duration,
                    chunks=[],
                    threshold=self.threshold,
                    model_path=str(self.model_path),
                )

            chunks = [
                VadAudioChunk(
                    segment=segment,
                    audio_data=_export_segment_to_ogg_bytes(wav_path, tmp_dir, index, segment),
                    content_type="audio/ogg",
                    filename_suffix=f".chunk-{index:04d}.ogg",
                )
                for index, segment in enumerate(segments, start=1)
            ]
            return VadSplitResult(
                raw_duration_seconds=raw_duration,
                chunks=chunks,
                threshold=self.threshold,
                model_path=str(self.model_path),
            )

    def _ensure_model(self) -> None:
        if self.model_path.exists():
            return
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        _logger.info("Downloading Silero VAD ONNX model to %s", self.model_path)
        with urllib.request.urlopen(self.model_url, timeout=30) as response:  # noqa: S310
            self.model_path.write_bytes(response.read())

    def _probabilities(self, wav_path: Path) -> list[float]:
        session = ort.InferenceSession(
            str(self.model_path),
            providers=["CPUExecutionProvider"],
        )
        audio = _read_wav_float32(wav_path)
        pad_samples = (-len(audio)) % WINDOW_SAMPLES
        if pad_samples:
            audio = np.pad(audio, (0, pad_samples))

        state = np.zeros(STATE_SHAPE, dtype=np.float32)
        context = np.zeros((1, CONTEXT_SAMPLES), dtype=np.float32)
        sample_rate = np.array(SAMPLE_RATE, dtype=np.int64)
        probabilities: list[float] = []
        for start in range(0, len(audio), WINDOW_SAMPLES):
            chunk = audio[start : start + WINDOW_SAMPLES].reshape(1, -1).astype(np.float32)
            model_input = np.concatenate([context, chunk], axis=1)
            output, state = session.run(
                None,
                {
                    "input": model_input,
                    "state": state,
                    "sr": sample_rate,
                },
            )
            context = model_input[:, -CONTEXT_SAMPLES:]
            probabilities.append(float(output[0][0]))
        return probabilities


def audio_duration_seconds(audio_data: bytes, filename: str | None = None) -> float | None:
    """Return audio duration in seconds without changing the audio."""
    if not audio_data:
        return 0.0

    wav_duration = _wav_duration_seconds_from_bytes(audio_data)
    if wav_duration is not None:
        return wav_duration

    with tempfile.TemporaryDirectory(prefix="ww-audio-duration-") as tmp_text:
        source_path = Path(tmp_text) / (filename or "input.audio")
        source_path.write_bytes(audio_data)
        result = subprocess.run(  # noqa: S603 - fixed executable args, no shell
            [
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(source_path),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
    if result.returncode != 0:
        _logger.debug("Could not detect audio duration: %s", result.stderr.strip())
        return None
    with suppress(ValueError):
        return round(float(result.stdout.strip()), 3)
    return None


def _ffmpeg_to_wav(source_path: Path, wav_path: Path) -> None:
    _run_ffmpeg(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-i",
            str(source_path),
            "-ac",
            "1",
            "-ar",
            str(SAMPLE_RATE),
            "-c:a",
            "pcm_s16le",
            str(wav_path),
        ]
    )


def _export_segment_to_ogg_bytes(
    wav_path: Path,
    tmp_dir: Path,
    index: int,
    segment: VadSegment,
) -> bytes:
    segment_path = tmp_dir / f"segment-{index:04d}.ogg"
    _run_ffmpeg(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-ss",
            f"{segment.start_seconds:.3f}",
            "-t",
            f"{segment.duration_seconds:.3f}",
            "-i",
            str(wav_path),
            "-c:a",
            "libopus",
            "-b:a",
            "18k",
            "-vbr",
            "on",
            str(segment_path),
        ]
    )
    return segment_path.read_bytes()


def _export_segments_to_ogg(wav_path: Path, output_path: Path, segments: list[VadSegment]) -> None:
    list_path = output_path.with_suffix(".json")
    segment_dir = output_path.parent / "segments"
    segment_dir.mkdir(parents=True, exist_ok=True)
    exported_paths: list[Path] = []
    for index, segment in enumerate(segments, start=1):
        segment_path = segment_dir / f"segment-{index:04d}.ogg"
        _run_ffmpeg(
            [
                "ffmpeg",
                "-hide_banner",
                "-y",
                "-ss",
                f"{segment.start_seconds:.3f}",
                "-t",
                f"{segment.duration_seconds:.3f}",
                "-i",
                str(wav_path),
                "-c:a",
                "libopus",
                "-b:a",
                "18k",
                "-vbr",
                "on",
                str(segment_path),
            ]
        )
        exported_paths.append(segment_path)

    concat_path = output_path.with_suffix(".txt")
    concat_path.write_text(
        "\n".join(f"file '{path.resolve()}'" for path in exported_paths) + "\n",
        encoding="utf-8",
    )
    _run_ffmpeg(
        [
            "ffmpeg",
            "-hide_banner",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-c",
            "copy",
            str(output_path),
        ]
    )
    list_path.write_text(json.dumps([asdict(segment) for segment in segments]) + "\n")


def _segments_from_probabilities(
    probabilities: list[float],
    threshold: float,
    *,
    min_speech_seconds: float = 0.25,
    min_silence_seconds: float = 0.45,
    speech_pad_seconds: float = 0.15,
) -> list[VadSegment]:
    step = WINDOW_SAMPLES / SAMPLE_RATE
    active = False
    start_time: float | None = None
    last_voice_time: float | None = None
    segments: list[VadSegment] = []
    for index, probability in enumerate(probabilities):
        time_seconds = index * step
        if probability >= threshold:
            if not active:
                active = True
                start_time = time_seconds
            last_voice_time = time_seconds + step
            continue

        silence_after_voice = (
            active
            and last_voice_time is not None
            and time_seconds - last_voice_time >= min_silence_seconds
        )
        if silence_after_voice:
            if start_time is not None and last_voice_time - start_time >= min_speech_seconds:
                segments.append(
                    VadSegment(
                        start_seconds=round(max(0.0, start_time - speech_pad_seconds), 3),
                        end_seconds=round(last_voice_time + speech_pad_seconds, 3),
                    )
                )
            active = False
            start_time = None
            last_voice_time = None

    if active and start_time is not None and last_voice_time is not None:
        if last_voice_time - start_time >= min_speech_seconds:
            segments.append(
                VadSegment(
                    start_seconds=round(max(0.0, start_time - speech_pad_seconds), 3),
                    end_seconds=round(last_voice_time + speech_pad_seconds, 3),
                )
            )

    return _merge_segments(segments, max_gap_seconds=0.25)


def _coalesce_segments(
    segments: list[VadSegment],
    *,
    min_chunk_duration_seconds: float,
    max_chunk_duration_seconds: float | None,
    max_chunk_gap_seconds: float,
) -> list[VadSegment]:
    config = VadCoalescingConfig(
        min_chunk_duration_seconds=min_chunk_duration_seconds,
        max_chunk_duration_seconds=max_chunk_duration_seconds,
        max_chunk_gap_seconds=max_chunk_gap_seconds,
    )
    if not segments:
        return []
    if config.min_chunk_duration_seconds <= 0 and config.max_chunk_gap_seconds <= 0:
        return segments

    coalesced = [segments[0]]
    for segment in segments[1:]:
        previous = coalesced[-1]
        gap_seconds = segment.start_seconds - previous.end_seconds
        merged = VadSegment(
            start_seconds=previous.start_seconds,
            end_seconds=segment.end_seconds,
        )
        if _should_coalesce_segment(
            previous,
            segment,
            merged,
            gap_seconds=gap_seconds,
            config=config,
        ):
            coalesced[-1] = merged
        else:
            coalesced.append(segment)
    return coalesced


def _should_coalesce_segment(
    previous: VadSegment,
    segment: VadSegment,
    merged: VadSegment,
    *,
    gap_seconds: float,
    config: VadCoalescingConfig,
) -> bool:
    if gap_seconds > config.max_chunk_gap_seconds:
        return False
    max_duration = config.max_chunk_duration_seconds
    if max_duration and merged.duration_seconds > max_duration:
        return False

    return (
        previous.duration_seconds < config.min_chunk_duration_seconds
        or segment.duration_seconds < config.min_chunk_duration_seconds
        or (max_duration is not None and merged.duration_seconds <= max_duration)
    )


def _merge_segments(segments: list[VadSegment], *, max_gap_seconds: float) -> list[VadSegment]:
    merged: list[VadSegment] = []
    for segment in segments:
        if not merged or segment.start_seconds - merged[-1].end_seconds > max_gap_seconds:
            merged.append(segment)
            continue
        previous = merged[-1]
        merged[-1] = VadSegment(
            start_seconds=previous.start_seconds,
            end_seconds=max(previous.end_seconds, segment.end_seconds),
        )
    return merged


def _read_wav_float32(wav_path: Path) -> np.ndarray:
    with wave.open(str(wav_path), "rb") as wav_file:
        raw = wav_file.readframes(wav_file.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _wav_duration_seconds(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as wav_file:
        return round(wav_file.getnframes() / wav_file.getframerate(), 3)


def _wav_duration_seconds_from_bytes(audio_data: bytes) -> float | None:
    with suppress(wave.Error, EOFError):
        with wave.open(io.BytesIO(audio_data), "rb") as wav_file:
            sample_rate = wav_file.getframerate()
            if sample_rate:
                return round(wav_file.getnframes() / sample_rate, 3)
    return None


def _duration_reduction_percent(original_duration: float, new_duration: float) -> float:
    if original_duration <= 0:
        return 0.0
    return round((1 - (new_duration / original_duration)) * 100, 1)


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(  # noqa: S603 - fixed executable args, no shell
        args,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
