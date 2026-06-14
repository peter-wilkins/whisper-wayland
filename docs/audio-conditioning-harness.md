# Audio Conditioning Harness

WhisperWayland hosts the first Linux experiment for Field Relay Audio
Conditioning. The harness is deliberately local-first and file-based:

```text
audio file
-> high-pass filter
-> VAD segments
-> local speech ranking
-> Opus chunks
-> transcription/cost comparison
```

Private audio, private transcripts, and run histories live under ignored
`local/audio-conditioning/`.

## Fixture Layout

Use fixture folders:

```text
local/audio-conditioning/fixtures/clean-001/
  source.wav
  fixture.json
```

`fixture.json`:

```json
{
  "id": "clean-001",
  "sourceFile": "source.wav",
  "acousticProfile": "clean",
  "scenario": "Clean indoor speech",
  "expectedWords": ["example"],
  "expectedSilence": false,
  "expectedSpeechWindows": [
    {"startSeconds": 1.0, "endSeconds": 12.0}
  ],
  "noiseNotes": "Quiet room",
  "notes": "Local-only fixture"
}
```

Supported profiles: `clean`, `fanwind`, `fieldmovement`, `outdoorwind`,
`nospeech`.

## Run

Without transcription:

```bash
.venv/bin/ww-audio-conditioning \
  local/audio-conditioning/fixtures
```

With OpenAI transcription comparison:

```bash
.venv/bin/ww-audio-conditioning \
  --transcribe \
  local/audio-conditioning/fixtures
```

Direct audio files also work:

```bash
.venv/bin/ww-audio-conditioning \
  /home/peter/continuum-core/data/landing-queue/audio-captures/artifacts/2026-06-12/example.wav
```

Pseudo-streaming replay can dry-run what would be sent to transcription without
calling any API:

```bash
.venv/bin/ww-audio-stream-replay \
  local/audio-conditioning/fixtures/raw-day-phone-wing-20260612/Voice\ 004_sd.m4a \
  --transcription-candidate-limit 5 \
  --transcription-min-score 0.7
```

Build and serve a local media player for a replay run:

```bash
.venv/bin/ww-audio-review \
  local/audio-conditioning/runs/<run-id> \
  --serve
```

Each run writes:

```text
local/audio-conditioning/runs/<run-id>/
  run.json
  report.md
  review.html
  conditioned/*.wav
  segments/*.opus
```

Pseudo-streaming replay also writes `topSpeechCandidates` in `run.json` and
adds rank/score/reason columns to `report.md`. The ranking pass is deliberately
cheap and local-only: it scores VAD candidates using PCM features such as RMS,
peak, zero-crossing rate, short-frame RMS variation, duration, and clipping
ratio. It does not transcribe, upload, or discard audio by itself.

The replay `transcriptionPlan` is also local-only. It selects the best ranked
non-overlapping candidate segments, estimates selected duration/bytes, and
keeps `transcriptionEnabled` false.

## Current Boundary

This is not Android/Kotlin work. Portable pieces are:

- FFmpeg filter graph: `highpass`
- FFmpeg VAD primitive: `silencedetect`
- Cheap local speech ranking from PCM features
- Opus chunk export
- JSON run/report schema
- acoustic profile thresholds

The harness accepts future Field Relay session audio files, but today the visible
local corpus is WhisperWayland capture tap audio under Continuum's
`audio-captures/artifacts/`.
