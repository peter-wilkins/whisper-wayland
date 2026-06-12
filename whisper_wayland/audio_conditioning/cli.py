"""Command line entrypoint for the audio conditioning harness."""

from __future__ import annotations

import argparse
from pathlib import Path

from whisper_wayland.audio_conditioning.harness import (
    DEFAULT_LOCAL_ROOT,
    AudioConditioningHarness,
)


def main(argv: list[str] | None = None) -> int:
    """Run the audio conditioning harness."""
    parser = argparse.ArgumentParser(
        description="Run local high-pass/VAD/Opus audio conditioning experiments.",
    )
    parser.add_argument(
        "fixtures",
        nargs="+",
        type=Path,
        help="Fixture folder, fixture.json, or direct audio file.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_LOCAL_ROOT,
        help="Local ignored output root.",
    )
    parser.add_argument("--run-id", help="Stable run id for repeatable test runs.")
    parser.add_argument(
        "--transcribe",
        action="store_true",
        help="Spend API calls to compare original and conditioned transcripts.",
    )
    args = parser.parse_args(argv)

    harness = AudioConditioningHarness(
        output_root=args.output_root,
        run_id=args.run_id,
        transcribe=args.transcribe,
    )
    results = harness.run_paths(args.fixtures)
    print(f"Wrote run: {harness.run_dir}")
    print(f"Fixtures: {len(results)}")
    return 0

