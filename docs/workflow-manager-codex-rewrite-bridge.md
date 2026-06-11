# Workflow Manager Codex Rewrite Bridge

Instructions for WhisperWaylandAgent.

## Goal

Improve Linux transcript extraction without starting a new model-hosting project.

Use Workflow Manager as Peter's local AI bridge:

- WhisperWayland captures audio and gets a raw transcript.
- A fast local rewrite endpoint cleans or extracts the intended insertion text.
- Slow Codex-agent work is allowed only off the paste-critical path.
- The final text insertion must never wait forever.

This is better than Copilot or a local LLM for this slice because it reuses the
system Peter already has: Codex context, agent skills, project dictionary, and
the future correction/dictionary pipeline.

## Current Reality

There is no synchronous "call Codex and return the answer" HTTP endpoint today.

Workflow Manager has an HTTP Phone Bridge:

```text
GET  http://127.0.0.1:8787/health
POST http://127.0.0.1:8787/v1/messages
```

`POST /v1/messages` appends a durable Bridge inbox event. A separate watcher can
inject that event into an already-running tmux Codex session. That is useful for
async agent work, but it is not suitable for the paste-critical path because the
HTTP response contains journey state, not the Codex answer.

WhisperWayland already has the right extension point:

```text
TEXT_POST_PROCESS_MODE=extract
TEXT_POST_PROCESS_PROVIDERS=local-api,local
TEXT_POST_PROCESS_LOCAL_API_URL=http://127.0.0.1:8765/v1/transcript/rewrite
TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS=1.5
```

Use that local rewrite API as the stable contract.

## Fast Rewrite API Contract

Build or call this endpoint on the local Linux machine:

```http
POST /v1/transcript/rewrite
Content-Type: application/json
```

Preferred request:

```json
{
  "principalId": "peter",
  "source": "whisper-wayland",
  "mode": "extract",
  "rawTranscriptText": "...",
  "captureId": "whisper-wayland:20260611T120000Z:abc123",
  "target": {
    "kind": "codex-terminal",
    "repoPath": "/home/peter/whisper-wayland"
  }
}
```

Compatibility note: current WhisperWayland may send this smaller payload:

```json
{
  "principalId": "local-user",
  "dictionaryScope": {
    "kind": "repo",
    "id": "whisper-wayland"
  },
  "rawTranscriptText": "...",
  "mode": "extract",
  "target": "codex-terminal"
}
```

The endpoint should accept both forms.

Response:

```json
{
  "insertionText": "...",
  "confidence": 0.9,
  "provider": "workflow-manager-codex",
  "backend": "workflow-manager-codex",
  "notes": []
}
```

Return both `provider` and `backend` for now. WhisperWayland currently reads
`backend`; Peter's preferred product contract says `provider`.

## Hard Requirements

1. Timeout must be short: 1.5s by default, never more than about 3s for the
   insertion path.
2. No blocking paste forever.
3. If the endpoint cannot produce a good answer in time, return no
   `insertionText` or return the raw/safest text, then let WhisperWayland fall
   back.
4. Do not call Codex synchronously unless a warm local service can reliably meet
   the timeout.
5. Record misses and corrections so a later Codex job can improve dictionaries.

## Recommended V0 Behavior

For the first working slice, the rewrite endpoint should be boring and fast:

1. Apply local dictionary fixes and deterministic cleanup.
2. If `mode=extract`, strip common dictation scaffolding and return the likely
   intended text.
3. If confidence is high, return `insertionText`.
4. If confidence is low, return an empty `insertionText` so WhisperWayland falls
   through to the next configured provider.
5. Queue an async Codex improvement request for later analysis.

Recommended WhisperWayland config while latency matters:

```text
TEXT_POST_PROCESS_MODE=extract
TEXT_POST_PROCESS_PROVIDERS=local-api,local
TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS=1.5
```

Only use `local-api,openai,local` when Peter explicitly wants higher quality and
accepts more latency.

## Async Codex Lane

Use this lane for dictionary learning, difficult extractions, and batch review.
Do not use it for immediate paste unless a later synchronous service is built.

Preferred local append command:

```bash
python3 /home/peter/workflow-manager/scripts/phone_bridge.py append-inbox \
  --journey-id whisper-wayland-loop \
  --body '<agent request here>' \
  --source whisper-wayland \
  --device-id linux-whisper \
  --user-id peter \
  --target whisperwayland \
  --membrane personal \
  --intent transcript_rewrite
```

HTTP alternative, if the Phone Bridge is running and auth is available:

```bash
curl -sS http://127.0.0.1:8787/v1/messages \
  -H "Authorization: Bearer $PHONE_BRIDGE_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "journeyId": "whisper-wayland-loop",
    "target": "whisperwayland",
    "membrane": "personal",
    "intent": "transcript_rewrite",
    "deviceId": "linux-whisper",
    "body": "Extract final intended insertion text from this transcript: ..."
  }'
```

The watcher route needs this local route in Workflow Manager:

```json
{
  "journeyId": "whisper-wayland-loop",
  "membrane": "personal",
  "target": "whisperwayland",
  "destinationType": "tmux-codex-session",
  "sessionName": "whisper-wayland",
  "action": "inject-message-for-chairman"
}
```

The watcher service must also be running:

```bash
cd /home/peter/workflow-manager
scripts/start_phone_chairman_watcher.sh
```

## Agent Prompt Shape

When queueing a Codex improvement request, keep it strict:

```text
You are improving a WhisperWayland transcript extraction.

Return JSON only:
{
  "insertionText": "...",
  "confidence": 0.0,
  "dictionaryCandidates": [],
  "notes": []
}

Mode: extract
Capture id: <capture-id>
Raw transcript:
<raw transcript>
```

For automation, prefer a deterministic local response file over scraping chat
output. Example:

```text
Write the JSON response to:
/home/peter/whisper-wayland/local/rewrite-responses/<capture-id>.json
```

Keep `local/` ignored. Do not push raw transcripts unless Peter explicitly says
they are safe.

## Next Implementation Slice

1. Add a tiny Workflow Manager local service at
   `http://127.0.0.1:8765/v1/transcript/rewrite`.
2. Make it accept both current WhisperWayland payloads and the preferred richer
   payload.
3. Add deterministic dictionary/extract cleanup first.
4. Add async Bridge queueing for low-confidence cases.
5. Add a regression test proving WhisperWayland returns quickly when the local
   API is slow or down.
