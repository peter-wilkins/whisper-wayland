"""Microphone level calibration CLI."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

import whisper_wayland as ww
from whisper_wayland.audio_recorder.level_meter import (
    AudioLevelStats,
    analyze_wav,
    recommended_volume_percent,
)


def main(argv: list[str] | None = None) -> int:
    """Run microphone calibration command."""
    parser = argparse.ArgumentParser(
        prog="whisper-wayland mic-check",
        description="Check microphone level for speech transcription.",
    )
    parser.add_argument("--config", help="Path to .env config file")
    parser.add_argument("--duration", type=float, default=5.0, help="Seconds to record")
    parser.add_argument(
        "--auto-adjust",
        action="store_true",
        help="Use pactl to set recommended source volume",
    )
    parser.add_argument(
        "--source",
        default="@DEFAULT_SOURCE@",
        help="Pulse/PipeWire source name, default @DEFAULT_SOURCE@",
    )
    parser.add_argument("--analyze-wav", type=Path, help="Analyze an existing WAV file")
    parser.add_argument(
        "--history",
        type=Path,
        help="Analyze latest WAV in a capture artifacts directory",
    )
    args = parser.parse_args(argv)

    try:
        audio_data = _load_audio_data(args)
        stats = analyze_wav(audio_data)
        current_volume = get_source_volume_percent(args.source)
        _print_report(stats, args.source, current_volume)

        if args.auto_adjust:
            _auto_adjust(args.source, stats, current_volume)

        return 0 if stats.verdict in {"ok", "loud"} else 2
    except Exception as e:
        print(f"Mic check failed: {e}", file=sys.stderr)
        return 1


def get_source_volume_percent(source: str = "@DEFAULT_SOURCE@") -> int | None:
    """Return Pulse/PipeWire source volume percent using pactl."""
    result = _run_pactl(["get-source-volume", source])
    if result.returncode != 0:
        return None
    match = re.search(r"/\s*(\d+)%", result.stdout)
    return int(match.group(1)) if match else None


def set_source_volume_percent(source: str, percent: int) -> bool:
    """Set Pulse/PipeWire source volume using pactl."""
    result = _run_pactl(["set-source-volume", source, f"{percent}%"])
    return result.returncode == 0


def _load_audio_data(args: argparse.Namespace) -> bytes:
    if args.analyze_wav:
        return args.analyze_wav.read_bytes()
    if args.history:
        latest = _latest_wav(args.history)
        print(f"Analyzing latest capture: {latest}")
        return latest.read_bytes()
    return _record_sample(args.config, args.duration)


def _latest_wav(path: Path) -> Path:
    candidates = sorted(path.glob("**/*.wav"), key=lambda p: p.stat().st_mtime)
    if not candidates:
        raise FileNotFoundError(f"No WAV files found under {path}")
    return candidates[-1]


def _record_sample(config_path: str | None, duration: float) -> bytes:
    if duration <= 0:
        raise ValueError("--duration must be positive")

    config = ww.Config.get(config_path)
    config.setup_logging()
    recorder = ww.AudioRecorder.new(config)
    print(f"Speak normally for {duration:.1f}s...")
    try:
        recorder.start_recording()
        time.sleep(duration)
        audio_data = recorder.stop_recording()
    finally:
        recorder.close()

    if not audio_data:
        raise RuntimeError("No audio captured")
    return audio_data


def _print_report(
    stats: AudioLevelStats,
    source: str,
    current_volume: int | None,
) -> None:
    print("Mic level report")
    print(f"  source: {source}")
    if current_volume is not None:
        print(f"  current source volume: {current_volume}%")
    else:
        print("  current source volume: unknown")
    print(f"  duration: {stats.duration_seconds:.3f}s")
    print(f"  sample rate: {stats.sample_rate_hz} Hz")
    print(f"  RMS: {stats.rms_dbfs:.1f} dBFS")
    print(f"  peak: {stats.peak_dbfs:.1f} dBFS")
    print(f"  clipping: {stats.clipping_percent:.3f}%")
    print(f"  verdict: {stats.verdict}")
    print(f"  recommendation: {stats.recommendation}")

    if current_volume is not None:
        recommended = recommended_volume_percent(stats, current_volume)
        if recommended != current_volume:
            print(f"  suggested command: pactl set-source-volume {source} {recommended}%")


def _auto_adjust(
    source: str,
    stats: AudioLevelStats,
    current_volume: int | None,
) -> None:
    if current_volume is None:
        print("  auto-adjust: skipped; could not read current volume")
        return

    recommended = recommended_volume_percent(stats, current_volume)
    if recommended == current_volume:
        print("  auto-adjust: no change")
        return

    if set_source_volume_percent(source, recommended):
        print(f"  auto-adjust: set {source} to {recommended}%")
    else:
        print("  auto-adjust: failed; adjust manually")


def _run_pactl(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["pactl", *args],
        check=False,
        capture_output=True,
        text=True,
    )
