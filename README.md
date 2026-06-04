# Whisper Wayland - Voice-to-Text Service

[![CI][ci-badge]][ci-url]

A push-to-talk voice transcription service that converts speech to text and inserts it at the cursor position in any application. Built for Ubuntu/Wayland without requiring root access.

## What is Whisper Wayland?

Whisper Wayland is a lightweight voice-to-text service that lets you dictate text directly into any application using a simple push-to-talk hotkey. Perfect for:

- **Writing emails and documents** - Dictate naturally instead of typing
- **Coding with voice** - Add comments or documentation quickly
- **Accessibility** - Alternative input method for users with typing difficulties
- **Multi-tasking** - Keep your hands free while entering text

The service runs in the background and works with any application that accepts text input - from web browsers to text editors to chat applications.

## Key Features

- **Push-to-Talk**: Hold Compose key to record, release to transcribe and insert
- **Universal Text Insertion**: Works with any application that accepts text input
- **Wayland Support**: Native support for modern Linux desktop environments
- **High Accuracy**: Uses OpenAI's Whisper API for accurate speech recognition
- **Privacy Focused**: Audio is only sent to OpenAI for transcription, not stored locally
- **Simple Deployment**: Runs natively on your Linux desktop

## Quick Start

### Prerequisites

You'll need:
- Ubuntu/Debian or Fedora/RHEL Linux system with Wayland
- [OpenAI API key][openai-api-keys] (pay-per-use, typically $0.006 per minute)
- Python 3.11+

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install portaudio19-dev python3-dev wtype

# Fedora/RHEL
sudo dnf install portaudio-devel python3-devel wtype
```

### Installation

#### Installation

1. **Install [uv][uv-install] package manager:**
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```

2. **Clone and install:**
   ```bash
   git clone https://github.com/rolandtritsch/whisper-wayland.git
   cd whisper-wayland
   uv sync
   ```

3. **Configure your API key:**
   ```bash
   # Create and configure .env file
   cp .env.example .env
   nano .env  # Add your OPENAI_API_KEY
   ```

4. **Run the service:**
   ```bash
   uv run whisper-wayland
   ```


## How to Use

1. **Start the service** using the installation method above
2. **Position your cursor** where you want text to appear in any application
3. **Press and hold the Compose key** (usually right Alt or Menu key)
4. **Speak clearly** while holding the key
5. **Release the key** - transcribed text appears at your cursor position

### Usage Tips

- **Speak naturally** - Whisper handles conversational speech well
- **Use punctuation commands** - Say "period", "comma", "question mark", etc.
- **Keep recordings under 30 seconds** - Default maximum recording duration
- **Ensure good audio quality** - Use a decent microphone for best results

## Configuration

All configuration is handled through environment variables and/or a/the `.env` file:

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key for Whisper service | - | Yes |
| `DEEPGRAM_API_KEY` | Optional Deepgram API key for `deepgram:<model>` transcription race targets | - | No |
| `WHISPER_MODEL` | OpenAI transcription model, or a legacy Whisper size alias | `gpt-4o-transcribe` | No |
| `TRANSCRIPTION_REQUEST_TIMEOUT_SECS` | Per-request timeout for transcription API calls | `20` | No |
| `TRANSCRIPTION_MAX_RETRIES` | App-level transcription retry count after timeout/API failure | `1` | No |
| `TRANSCRIPTION_RACE_MODELS` | Optional comma-separated extra transcription targets to race in parallel; supports OpenAI model names, `deepgram:<model>`, and `openai-compatible:<base-url>#<model>` | - | No |
| `AUDIO_SAMPLE_RATE` | Audio recording sample rate | `16000` | No |
| `AUDIO_PREROLL_SECONDS` | Local pre-roll audio prepended when push-to-talk starts (`0` to `3`) | `1.0` | No |
| `AUDIO_INPUT_DEVICE_INDEX` | Explicit PyAudio input device index, blank for auto-selection | - | No |
| `AUDIO_INPUT_DEVICE_NAME` | Case-insensitive input device name substring, blank for auto-selection | - | No |
| `MAX_RECORDING_DURATION` | Maximum recording duration in seconds | `30` | No |
| `AUDIO_TRANSCRIPTION_NORMALIZATION_ENABLED` | Normalize audio sent to the transcription API only | `false` | No |
| `AUDIO_TRANSCRIPTION_NORMALIZATION_TARGET_RMS_DBFS` | Target RMS level for transcription-only normalization | `-22` | No |
| `AUDIO_TRANSCRIPTION_NORMALIZATION_MAX_PEAK_AMPLITUDE` | Peak ceiling for transcription-only normalization | `0.95` | No |
| `AUDIO_TRANSCRIPTION_NORMALIZATION_MAX_GAIN` | Maximum gain multiplier for transcription-only normalization | `6` | No |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | `INFO` | No |
| `HOTKEY` | Push-to-talk key or mouse-button combination | `ctrl+compose` | No |
| `HOTKEY_MODE` | Activation mode (`push_to_talk` or `toggle`) | `push_to_talk` | No |
| `TEXT_INSERTION_METHOD` | Text insertion backend (`auto`, `tmux`, `ydotool`, `wtype`, `xdotool`, or `clipboard`) | `auto` | No |
| `TEXT_TMUX_TARGET_PANE` | Explicit tmux pane target for `TEXT_INSERTION_METHOD=tmux`, e.g. `%1` or `session:0.0` | - | No |
| `TEXT_PASTE_HOTKEY` | Paste shortcut for clipboard fallback insertion (`ctrl+v` or `ctrl+shift+v`) | `ctrl+v` | No |
| `TEXT_POST_PROCESS_MODE` | Rewrite transcript before insertion (`raw`, `clean`, `snappy`, or `caveman`) | `raw` | No |
| `TEXT_POST_PROCESS_MODEL` | OpenAI text model for transcript rewriting, or `local` for local caveman cleanup | `gpt-4.1-mini` | No |
| `TEXT_POST_PROCESS_PROVIDERS` | Ordered comma-separated rewrite providers (`local-api`, `openai`, `local`) | `openai,local` | No |
| `TEXT_POST_PROCESS_LOCAL_API_URL` | Same-machine personal dictionary rewrite API endpoint | `http://127.0.0.1:8765/v1/transcript/rewrite` | No |
| `TEXT_POST_PROCESS_LOCAL_API_TIMEOUT_SECS` | Timeout for local API transcript rewrite requests | `1.5` | No |
| `CONTINUUM_CAPTURE_INLET_DIR` | Optional local Continuum audio capture file-drop directory | - | No |
| `STREAMING_TRANSCRIPTION_ENABLED` | Enable experimental OpenAI Realtime streaming transcription | `false` | No |
| `STREAMING_TRANSCRIPTION_MODEL` | Model for Realtime streaming transcription | `gpt-realtime-whisper` | No |
| `STREAMING_SAMPLE_RATE` | PCM sample rate sent to Realtime streaming transcription | `24000` | No |
| `STREAMING_COMPLETION_TIMEOUT_SECS` | Seconds to wait for final streaming transcript after release | `4` | No |
| `STREAMING_DELTA_IDLE_TIMEOUT_SECS` | Seconds to wait after the last partial realtime transcript before using it | `0.75` | No |
| `STREAMING_TURN_DETECTION_ENABLED` | Commit and insert completed speech chunks on pauses | `false` | No |
| `STREAMING_VAD_SILENCE_DURATION_MS` | Pause length before a streaming speech chunk is finalized | `700` | No |

Mouse-button hotkeys are supported via evdev. Useful values include `mouse_left`,
`mouse_middle`, `mouse_right`, `mouse_side`, `mouse_extra`, `mouse_back`, and
`mouse_forward`. Mouse events are observed, not consumed, so the click still
reaches the focused application. With `HOTKEY_MODE=toggle`, each click alternates
recording on/off.

### Model Selection Guide

- **gpt-4o-transcribe**: Best default for dictation accuracy
- **gpt-4o-mini-transcribe**: Lower-latency/lower-cost alternative
- **whisper-1**: Legacy hosted Whisper model
- **tiny/base/small/medium/large**: Legacy aliases mapped to `whisper-1`

## Troubleshooting

### Common Issues

**Audio not recording:**
- Check your user is in the `audio` group: `sudo usermod -a -G audio $USER`
- Log out and back in after group changes
- Test microphone: `arecord -d 5 test.wav && aplay test.wav`
- Check speech levels: `.venv/bin/whisper-wayland mic-check --duration 5`
- Auto-adjust default mic volume: `.venv/bin/whisper-wayland mic-check --duration 5 --auto-adjust`

Good speech capture usually has RMS near `-30` to `-16` dBFS, peaks below about
`-3` dBFS, and clipping below `0.1%`. The mic checker records locally only and
does not upload audio. To inspect existing Continuum capture files, run:

```bash
.venv/bin/whisper-wayland mic-check --history /home/peter/continuum-core/data/landing-queue/audio-captures/artifacts
```

For automatic checks after recordings, set `AUDIO_LEVEL_MONITOR_ENABLED=true`.
By default this logs suggestions only. `AUDIO_LEVEL_AUTO_ADJUST_ENABLED=true`
means the service should try to fix bad levels, and
`AUDIO_LEVEL_MANAGE_MICS_ENABLED=true` is explicit permission to change system
mic settings. Actual OS volume changes require both flags.
`AUDIO_LEVEL_CHECK_INTERVAL_SECS` controls the cooldown between checks.

For quiet microphones, `AUDIO_TRANSCRIPTION_NORMALIZATION_ENABLED=true` can
boost the WAV sent to the transcription API. This does not change local Continuum
capture artifacts; those remain the raw recording bytes.

**Text not inserting:**
- Verify `wtype` is installed: `which wtype`
- Test manually: `echo "test" | wtype -`
- Check Wayland environment variables are set
- Use `TEXT_INSERTION_METHOD=auto` to prefer direct typing. The explicit
  `clipboard` backend may be captured by clipboard history managers before the
  previous clipboard is restored.

**Hotkey not working:**
- Verify Compose key is configured: e.g. `setxkbmap -option compose:lctrl`
- Check if another application is using the key
- Try alternative keys by setting `HOTKEY` environment variable

**Service fails to start:**
- Check your OpenAI API key is valid
- Ensure all system dependencies are installed
- Enable debug logging: `LOG_LEVEL=DEBUG`

## TODO / Issues

### Streaming transcription rollout

Experimental streaming transcription is implemented behind
`STREAMING_TRANSCRIPTION_ENABLED=true`. The app streams microphone audio while the
hotkey is active, finalizes transcription on release, and inserts only the final
transcript. If streaming fails or returns no transcript, captured audio is converted
to WAV and sent through the existing batch transcription path.

When `STREAMING_TURN_DETECTION_ENABLED=true`, the Realtime API uses server-side
voice activity detection to finalize completed speech chunks during longer
recordings. Completed chunks are aggregated and inserted once when recording
stops, after any configured transcript post-processing.

Remaining rough edges:
- Confirm account/model access for higher-accuracy batch transcription models.
- Tune streaming sample rate and chunk size for latency on real hardware.
- Add correction-aware partial text insertion before typing unstable interim text.

### Getting Help

For detailed troubleshooting and logs:

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG
uv run whisper-wayland
```

## Cost Considerations

Whisper Wayland uses OpenAI's API on a pay-per-use basis:
- **Typical usage**: $0.006 per minute of audio
- **Example**: 1 hour of dictation per day ≈ $10-15/month
- **Factors**: Longer recordings and higher-quality models cost more

## Privacy & Security

- **Audio processing**: Audio is sent to OpenAI for transcription only
- **No local storage by default**: Audio data is not saved locally unless `CONTINUUM_CAPTURE_INLET_DIR` is set
- **Opt-in Continuum capture**: When enabled, batch recordings are written only to local WAV/JSON files before text insertion
- **API key security**: Store your API key securely in `.env` file
- **Network only**: Service only activates when you press the hotkey

## Support & Contributing

- **Issues**: Report bugs and request features on [GitHub Issues][issues-url]
- **Contributing**: See [CLAUDE.md][claude-md] for development guidelines
- **Discussions**: Join community discussions on [GitHub Discussions][discussions-url]

## License

MIT License - see [LICENSE][license-url] file for details.

---

**For developers**: See [CLAUDE.md][claude-md] for architecture details, development workflow, and contribution guidelines.

[ci-badge]: https://github.com/rolandtritsch/whisper-wayland/actions/workflows/ci.yml/badge.svg
[ci-url]: https://github.com/rolandtritsch/whisper-wayland/actions/workflows/ci.yml
[openai-api-keys]: https://platform.openai.com/api-keys
[uv-install]: https://docs.astral.sh/uv/getting-started/installation/
[issues-url]: https://github.com/rolandtritsch/whisper-wayland/issues
[discussions-url]: https://github.com/rolandtritsch/whisper-wayland/discussions
[license-url]: https://github.com/rolandtritsch/whisper-wayland/blob/trunk/LICENSE
[claude-md]: https://github.com/rolandtritsch/whisper-wayland/blob/trunk/CLAUDE.md
