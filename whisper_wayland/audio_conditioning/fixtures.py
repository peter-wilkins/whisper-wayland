"""Fixture loading for local audio conditioning experiments."""

from __future__ import annotations

import json
from pathlib import Path

from whisper_wayland.audio_conditioning.models import Fixture
from whisper_wayland.audio_conditioning.profiles import DEFAULT_PROFILE_NAME

SUPPORTED_AUDIO_SUFFIXES = {".wav", ".m4a", ".mp3", ".opus", ".flac", ".aac"}


def load_fixtures(paths: list[Path]) -> list[Fixture]:
    """Load fixture folders, fixture JSON files, or direct audio files."""
    fixtures: list[Fixture] = []
    for path in paths:
        expanded = path.expanduser()
        if expanded.is_dir():
            fixture_json = expanded / "fixture.json"
            if fixture_json.exists():
                fixtures.append(load_fixture_json(fixture_json))
                continue
            fixtures.extend(
                load_fixture_json(child)
                for child in sorted(expanded.glob("*/fixture.json"))
            )
            direct_audio = [
                child
                for child in sorted(expanded.iterdir())
                if child.is_file() and child.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES
            ]
            fixtures.extend(fixture_from_audio_file(child) for child in direct_audio)
            continue

        if expanded.name == "fixture.json" or expanded.suffix.lower() == ".json":
            fixtures.append(load_fixture_json(expanded))
            continue

        fixtures.append(fixture_from_audio_file(expanded))

    return fixtures


def load_fixture_json(path: Path) -> Fixture:
    """Load one fixture sidecar JSON."""
    payload = json.loads(path.read_text())
    source_name = payload.get("sourceFile") or payload.get("source_path") or "source.wav"
    source_path = Path(source_name)
    if not source_path.is_absolute():
        source_path = path.parent / source_path

    return Fixture(
        fixture_id=str(payload.get("id") or path.parent.name),
        source_path=source_path,
        acoustic_profile=str(payload.get("acousticProfile") or DEFAULT_PROFILE_NAME),
        scenario=str(payload.get("scenario") or path.parent.name),
        expected_words=[str(word) for word in payload.get("expectedWords", [])],
        expected_silence=bool(payload.get("expectedSilence", False)),
        expected_speech_windows=list(payload.get("expectedSpeechWindows", [])),
        noise_notes=str(payload.get("noiseNotes") or ""),
        notes=str(payload.get("notes") or ""),
    )


def fixture_from_audio_file(path: Path) -> Fixture:
    """Create a minimal fixture from a direct audio path."""
    return Fixture(
        fixture_id=_fixture_id_from_path(path),
        source_path=path,
        acoustic_profile=DEFAULT_PROFILE_NAME,
        scenario=path.stem,
        expected_words=[],
        expected_silence=False,
        expected_speech_windows=[],
        noise_notes="",
        notes="Direct audio file without fixture metadata.",
    )


def _fixture_id_from_path(path: Path) -> str:
    clean = "".join(char.lower() if char.isalnum() else "-" for char in path.stem)
    return "-".join(part for part in clean.split("-") if part) or "audio-fixture"
