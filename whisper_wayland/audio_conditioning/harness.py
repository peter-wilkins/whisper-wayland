"""Repeatable local audio conditioning experiment harness."""

from __future__ import annotations

import os
import typing
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from whisper_wayland.audio_conditioning.ffmpeg_tools import (
    detect_speech_segments,
    export_opus_segment,
    highpass_to_wav,
    probe_duration_seconds,
)
from whisper_wayland.audio_conditioning.fixtures import load_fixtures
from whisper_wayland.audio_conditioning.models import (
    Fixture,
    FixtureResult,
    SegmentArtifact,
    TranscriptionResult,
)
from whisper_wayland.audio_conditioning.profiles import profile_for_name
from whisper_wayland.audio_conditioning.reporting import write_report, write_run_json

DEFAULT_LOCAL_ROOT = Path("local/audio-conditioning")
ESTIMATED_TRANSCRIPTION_PRICE_PER_MINUTE_USD = 0.006


class AudioConditioningHarness:
    """Run local high-pass/VAD/Opus experiments over fixture audio."""

    def __init__(
        self,
        output_root: Path = DEFAULT_LOCAL_ROOT,
        run_id: str | None = None,
        transcribe: bool = False,
    ) -> None:
        """Create a harness instance."""
        self.output_root = output_root
        self.run_id = run_id or _utc_run_id()
        self.transcribe = transcribe
        self.run_dir = output_root / "runs" / self.run_id
        self.segments_dir = self.run_dir / "segments"
        self.conditioned_dir = self.run_dir / "conditioned"

    def run_paths(self, fixture_paths: list[Path]) -> list[FixtureResult]:
        """Load and run fixture paths."""
        fixtures = load_fixtures(fixture_paths)
        return self.run_fixtures(fixtures)

    def run_fixtures(self, fixtures: list[Fixture]) -> list[FixtureResult]:
        """Run the conditioning pipeline over fixtures and write reports."""
        self.segments_dir.mkdir(parents=True, exist_ok=True)
        self.conditioned_dir.mkdir(parents=True, exist_ok=True)

        results = [self._run_fixture(fixture) for fixture in fixtures]
        run_payload = self._run_payload(results)
        write_run_json(self.run_dir / "run.json", run_payload)
        write_report(self.run_dir / "report.md", self.run_id, results)
        return results

    def _run_fixture(self, fixture: Fixture) -> FixtureResult:
        profile = profile_for_name(fixture.acoustic_profile)
        duration_seconds = probe_duration_seconds(fixture.source_path)
        original_size = fixture.source_path.stat().st_size
        conditioned_wav = self.conditioned_dir / f"{fixture.fixture_id}-highpass.wav"

        highpass_to_wav(fixture.source_path, conditioned_wav, profile)
        conditioned_size = conditioned_wav.stat().st_size
        segments = detect_speech_segments(conditioned_wav, duration_seconds, profile)
        artifacts = [
            self._export_segment(conditioned_wav, fixture.fixture_id, segment, profile)
            for segment in segments
        ]
        kept_duration = round(sum(segment.duration_seconds for segment in segments), 3)
        discarded_duration = round(max(0.0, duration_seconds - kept_duration), 3)
        opus_size = sum(artifact.byte_length for artifact in artifacts)
        saving = _size_reduction_percent(original_size, opus_size)
        transcription = self._transcribe_fixture(fixture, artifacts) if self.transcribe else None
        passed, failure_reasons = _evaluate_fixture(
            fixture=fixture,
            kept_duration_seconds=kept_duration,
            transcription=transcription,
        )

        return FixtureResult(
            fixture=fixture,
            profile=asdict(profile),
            original_duration_seconds=duration_seconds,
            original_byte_length=original_size,
            conditioned_wav_byte_length=conditioned_size,
            kept_duration_seconds=kept_duration,
            discarded_duration_seconds=discarded_duration,
            opus_byte_length=opus_size,
            upload_size_reduction_percent=saving,
            detected_segments=segments,
            segment_artifacts=artifacts,
            transcription=transcription,
            passed=passed,
            failure_reasons=failure_reasons,
        )

    def _export_segment(
        self,
        conditioned_wav: Path,
        fixture_id: str,
        segment: typing.Any,
        profile: typing.Any,
    ) -> SegmentArtifact:
        output_path = self.segments_dir / f"{fixture_id}-seg-{segment.index:03d}.opus"
        export_opus_segment(conditioned_wav, output_path, segment, profile)
        return SegmentArtifact(
            segment=segment,
            path=output_path.relative_to(self.run_dir),
            byte_length=output_path.stat().st_size,
        )

    def _transcribe_fixture(
        self,
        fixture: Fixture,
        artifacts: list[SegmentArtifact],
    ) -> TranscriptionResult:
        try:
            return _transcribe_with_openai(fixture.source_path, artifacts, self.run_dir)
        except Exception as e:
            return TranscriptionResult(
                original_text=None,
                conditioned_text=None,
                error=str(e),
            )

    def _run_payload(self, results: list[FixtureResult]) -> dict[str, typing.Any]:
        original_seconds = sum(result.original_duration_seconds for result in results)
        kept_seconds = sum(result.kept_duration_seconds for result in results)
        original_bytes = sum(result.original_byte_length for result in results)
        opus_bytes = sum(result.opus_byte_length for result in results)
        return {
            "schema": "whisper_wayland.audio_conditioning.run.v1",
            "runId": self.run_id,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "transcriptionEnabled": self.transcribe,
            "priceAssumption": {
                "transcriptionUsdPerMinute": ESTIMATED_TRANSCRIPTION_PRICE_PER_MINUTE_USD,
            },
            "summary": {
                "fixtureCount": len(results),
                "originalDurationSeconds": round(original_seconds, 3),
                "keptDurationSeconds": round(kept_seconds, 3),
                "discardedDurationSeconds": round(max(0.0, original_seconds - kept_seconds), 3),
                "originalByteLength": original_bytes,
                "opusByteLength": opus_bytes,
                "uploadSizeReductionPercent": _size_reduction_percent(
                    original_bytes,
                    opus_bytes,
                ),
                "estimatedOriginalCostUsd": _estimated_cost(original_seconds),
                "estimatedConditionedCostUsd": _estimated_cost(kept_seconds),
            },
            "results": results,
        }


def _evaluate_fixture(
    fixture: Fixture,
    kept_duration_seconds: float,
    transcription: TranscriptionResult | None,
) -> tuple[bool, list[str]]:
    failure_reasons: list[str] = []
    if fixture.expected_silence and kept_duration_seconds > 0:
        failure_reasons.append("expected silence but VAD kept speech-like audio")
    if not fixture.expected_silence and kept_duration_seconds <= 0:
        failure_reasons.append("expected speech but VAD found no speech-like audio")

    if transcription and fixture.expected_words:
        conditioned_text = (transcription.conditioned_text or "").lower()
        missing = [
            word for word in fixture.expected_words if word.lower() not in conditioned_text
        ]
        if missing:
            failure_reasons.append(f"missing expected words: {', '.join(missing)}")

    return not failure_reasons, failure_reasons


def _size_reduction_percent(original_size: int, new_size: int) -> float:
    if original_size <= 0:
        return 0.0
    return round((1 - (new_size / original_size)) * 100, 1)


def _estimated_cost(duration_seconds: float) -> float:
    return round((duration_seconds / 60) * ESTIMATED_TRANSCRIPTION_PRICE_PER_MINUTE_USD, 6)


def _utc_run_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _transcribe_with_openai(
    source_path: Path,
    artifacts: list[SegmentArtifact],
    run_dir: Path,
) -> TranscriptionResult:
    import openai
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return TranscriptionResult(
            original_text=None,
            conditioned_text=None,
            error="OPENAI_API_KEY is not configured",
        )

    client = openai.OpenAI(api_key=api_key)
    original_text = _transcribe_file(client, source_path)
    conditioned_text_parts = [
        _transcribe_file(client, run_dir / artifact.path) for artifact in artifacts
    ]
    return TranscriptionResult(
        original_text=original_text,
        conditioned_text=" ".join(part for part in conditioned_text_parts if part).strip(),
        error=None,
    )


def _transcribe_file(client: typing.Any, path: Path) -> str:
    with path.open("rb") as audio_file:
        response = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language="en",
            response_format="text",
        )
    return str(response).strip()

