# Pre-Transcription Chunking Plan

## Goal

Reduce post-release latency for long, rambly push-to-talk recordings by doing
speech-to-text work before the user releases the hotkey, while preserving the
current UX: paste one final extracted blob after recording stops.

## Resolved Decisions

- Use pre-transcription chunking: transcribe closed speech chunks during
  recording, then run one extraction/post-processing pass after the complete
  ordered transcript is ready.
- Define closed chunks with conservative local Silero VAD silence boundaries,
  not fixed time windows.
- Start chunking only after a short recording-duration threshold, initially
  around 10 seconds, so short exact messages stay on the simpler batch path.
- Preserve timeline order by assembling chunk transcripts by audio start time,
  never by API completion order.
- Do not run speculative extraction in v1.
- Add small audio padding around chunk boundaries. Slight duplicate words are
  acceptable; missing first or last words are worse.
- Use the existing transcription client and provider race setup initially.
  Chunking changes provider latency and quality dynamics, so provider comparison
  remains part of the experiment.
- Do not impose a product cap on total chunks, but keep a high implementation
  safety ceiling to prevent runaway API traffic if VAD misbehaves.
- Keep chunking behind a feature flag until latency, quality, insertion
  behavior, and API cost have been tested.
- Keep Continuum capture reporting as one intentional capture. Full raw audio,
  final raw transcript, and final insertion text stay unchanged; chunk metadata
  is diagnostic.
- Build a replay harness from existing local capture WAV files before changing
  the live recorder path.

## First Slice

Add a local replay command that:

1. Accepts an existing local audio file.
2. Runs Silero VAD chunk detection.
3. Writes local chunk audio and chunk timing metadata under ignored `local/`.
4. Optionally transcribes chunks only when `--transcribe` is passed.
5. Assembles chunk transcripts by audio timeline order.
6. Performs no insertion and writes nothing to Continuum.

Dry run:

```bash
.venv/bin/python -m whisper_wayland.pretranscription_replay path/to/capture.wav
```

API-spending transcript comparison:

```bash
.venv/bin/python -m whisper_wayland.pretranscription_replay path/to/capture.wav --transcribe
```

## Replay Finding

The first transcription replay on a 45 second dictation split the audio into 13
micro-chunks. It completed without chunk failures, but very short chunks hurt
transcription quality by removing context around ambiguous words. Replay should
therefore coalesce adjacent VAD regions into phrase-sized chunks before live
integration is attempted.

With default coalescing settings, the same recording produced 5 phrase chunks.
Quality improved: chunking no longer produced standalone filler fragments and
the word "read" was no longer misrecognized as "red". Provider choice still
matters. On this sample, OpenAI `whisper-1` on the coalesced chunks recognized
"switch tacks" correctly, while Deepgram `nova-3` and the current race path
misrecognized it as "switch tax".
