# Whisper Wayland Context

## Terms

### Pre-transcription chunking

During an intentional push-to-talk recording, Whisper Wayland may split closed
speech regions into chunks and transcribe those chunks before the user releases
the hotkey. The chunk transcripts are accumulated as raw transcript text. After
the user releases the hotkey, Whisper Wayland runs one extraction/post-processing
pass over the complete accumulated transcript and inserts one final text blob.

### Closed speech chunk

A closed speech chunk is a speech region that has ended according to conservative
local VAD silence detection.

### Chunking activation threshold

The chunking activation threshold is the recording duration after which
Whisper Wayland may begin early transcription of closed speech chunks.

### Chunk fallback

Chunk fallback is the rule that pre-transcription chunking must not lose speech.
If early chunk transcription is incomplete, slow, or failed when recording stops,
Whisper Wayland falls back to transcribing the missing audio span or the complete
recording rather than inserting a partial message.

### Timeline transcript assembly

Timeline transcript assembly combines chunk transcripts according to their audio
start time, not the order in which transcription jobs finish.

### Final extraction

Final extraction is the single post-processing pass run after the complete
ordered raw transcript is available.

### Chunk boundary padding

Chunk boundary padding keeps a small amount of audio before and after each
closed speech chunk. Whisper Wayland prefers slight duplicate transcript text at
chunk boundaries over missing first or last words.

### Chunk transcription provider

The chunk transcription provider is the speech-to-text backend used for an
individual closed speech chunk.

### Chunk concurrency safety ceiling

The chunk concurrency safety ceiling is a guard that prevents runaway parallel
transcription if local chunk detection misbehaves.

### Pre-transcription chunking feature flag

The pre-transcription chunking feature flag controls whether the chunked path or
the batch transcription path is used for a recording.

### Chunked capture reporting

Chunked capture reporting preserves one user-level intentional capture. The raw
audio artifact remains the full original recording, and final transcript fields
remain the assembled raw transcript and final insertion text. Chunk details are
internal metadata for diagnostics rather than separate capture artifacts.

### Pre-transcription replay

Pre-transcription replay runs chunk detection and optional chunk transcription
against an existing local audio file.
