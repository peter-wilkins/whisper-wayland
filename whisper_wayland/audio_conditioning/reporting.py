"""Report writers for audio conditioning runs."""

from __future__ import annotations

import json
import typing
from dataclasses import asdict, is_dataclass
from pathlib import Path

from whisper_wayland.audio_conditioning.models import FixtureResult


def write_run_json(path: Path, payload: dict[str, typing.Any]) -> None:
    """Write machine-readable run output."""
    path.write_text(json.dumps(payload, indent=2, default=_json_default) + "\n")


def write_report(path: Path, run_id: str, results: list[FixtureResult]) -> None:
    """Write human-readable markdown summary."""
    lines = [
        f"# Audio Conditioning Run {run_id}",
        "",
        "| Fixture | Profile | Original | Kept | Opus | Size Saving | Pass |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]

    for result in results:
        lines.append(
            "| "
            f"{result.fixture.fixture_id} | "
            f"{result.fixture.acoustic_profile} | "
            f"{result.original_duration_seconds:.2f}s / {result.original_byte_length} B | "
            f"{result.kept_duration_seconds:.2f}s | "
            f"{result.opus_byte_length} B | "
            f"{result.upload_size_reduction_percent:.1f}% | "
            f"{'yes' if result.passed else 'no'} |"
        )

    for result in results:
        lines.extend(
            [
                "",
                f"## {result.fixture.fixture_id}",
                "",
                f"- Scenario: {result.fixture.scenario}",
                f"- Noise notes: {result.fixture.noise_notes or 'none'}",
                f"- Original bytes: {result.original_byte_length}",
                f"- Conditioned WAV bytes: {result.conditioned_wav_byte_length}",
                f"- Opus bytes: {result.opus_byte_length}",
                f"- Kept/discarded: {result.kept_duration_seconds:.2f}s / "
                f"{result.discarded_duration_seconds:.2f}s",
                f"- Result: {'pass' if result.passed else 'fail'}",
            ]
        )
        if result.failure_reasons:
            lines.append(f"- Failure reasons: {'; '.join(result.failure_reasons)}")
        if result.detected_segments:
            lines.append("- Segments:")
            for segment in result.detected_segments:
                lines.append(
                    f"  - {segment.index}: {segment.start_seconds:.3f}s"
                    f"-{segment.end_seconds:.3f}s ({segment.duration_seconds:.3f}s)"
                )
        else:
            lines.append("- Segments: none")

        if result.transcription:
            lines.extend(
                [
                    "- Original transcript: "
                    f"{_private_text(result.transcription.original_text)}",
                    "- Conditioned transcript: "
                    f"{_private_text(result.transcription.conditioned_text)}",
                ]
            )
            if result.transcription.error:
                lines.append(f"- Transcription error: {result.transcription.error}")

    path.write_text("\n".join(lines) + "\n")


def _private_text(text: str | None) -> str:
    if not text:
        return ""
    return text


def _json_default(value: typing.Any) -> typing.Any:
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

