"""OpenAI realtime streaming transcription client."""

import asyncio
import base64
import io
import json
import logging
import queue
import threading
import time
import typing
import wave
from dataclasses import dataclass

import pyaudio
import websockets

import whisper_wayland as ww
from whisper_wayland.audio_recorder.audio_system_validator import AudioSystemValidator

_logger = logging.getLogger(__name__)


@dataclass
class StreamingTranscriptionResult:
    """Result returned when a streaming transcription session ends."""

    text: str = ""
    fallback_audio: typing.Optional[bytes] = None
    error: typing.Optional[str] = None
    chunks_delivered: bool = False


class RealtimeStreamingTranscriptionClient:
    """Streams microphone audio to OpenAI Realtime transcription."""

    REALTIME_URL = "wss://api.openai.com/v1/realtime?intent=transcription"
    MIN_COMMIT_AUDIO_SECS = 0.1
    WEBSOCKET_SHUTDOWN_GRACE_SECS = 1.0

    def __init__(
        self,
        config: "ww.Config",
        audio: typing.Optional[pyaudio.PyAudio] = None,
        transcript_callback: typing.Optional[typing.Callable[[str], None]] = None,
    ) -> None:
        """Initialize realtime streaming client."""
        self._config = config
        self._audio = audio or pyaudio.PyAudio()
        self._transcript_callback = transcript_callback
        self._owns_audio = audio is None
        self._audio_validator = AudioSystemValidator.new()
        self._input_device_index = self._audio_validator.find_preferred_input_device(
            self._audio,
            config,
        )
        input_device_name = self._audio_validator.get_input_device_name(
            self._audio,
            self._input_device_index,
        )
        _logger.info(
            f"Realtime streaming input device: {input_device_name} "
            f"(index {self._input_device_index})"
        )
        self._lock = threading.Lock()
        self._audio_queue: queue.Queue[typing.Optional[bytes]] = queue.Queue()
        self._stop_event = threading.Event()
        self._audio_started_event = threading.Event()
        self._audio_thread: typing.Optional[threading.Thread] = None
        self._websocket_thread: typing.Optional[threading.Thread] = None
        self._frames: list[bytes] = []
        self._transcript_parts: list[str] = []
        self._last_transcript_event_at: typing.Optional[float] = None
        self._chunks_delivered = False
        self._error: typing.Optional[str] = None
        self._streaming = False
        self._cancel_requested = False

    def start(self) -> bool:
        """Start recording and streaming audio.

        Returns:
            True when microphone capture started, False otherwise.
        """
        with self._lock:
            if self._streaming:
                _logger.warning("Realtime streaming already active")
                return True

            self._reset_state()
            self._streaming = True
            self._websocket_thread = threading.Thread(
                target=self._run_websocket_thread,
                daemon=True,
            )
            self._audio_thread = threading.Thread(target=self._record_audio_loop, daemon=True)
            self._websocket_thread.start()
            self._audio_thread.start()

        if self._audio_started_event.wait(timeout=2.0) and not self._error:
            _logger.info("Realtime streaming transcription started")
            return True

        if not self._error:
            _logger.error("Realtime streaming audio capture did not start")
        self._stop_event.set()
        self._streaming = False
        return False

    def stop(self) -> StreamingTranscriptionResult:
        """Stop streaming and return the final transcript or fallback audio."""
        self._stop_event.set()

        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=5.0)

        self._audio_queue.put(None)

        timeout = self._stop_join_timeout_secs()
        if self._websocket_thread and self._websocket_thread.is_alive():
            self._websocket_thread.join(timeout=timeout)
            if self._websocket_thread.is_alive():
                _logger.warning("Realtime websocket did not finish before fallback timeout")

        with self._lock:
            self._streaming = False

        text = self._combined_transcript_text()
        if text:
            _logger.info("Realtime streaming transcription completed")
            return StreamingTranscriptionResult(text=text)

        if self._chunks_delivered:
            _logger.info("Realtime streaming transcription completed with delivered chunks")
            return StreamingTranscriptionResult(chunks_delivered=True)

        audio_duration_secs = self._captured_audio_duration_secs()
        fallback_audio = (
            self._frames_to_wav()
            if self._frames and audio_duration_secs >= self.MIN_COMMIT_AUDIO_SECS
            else None
        )
        if fallback_audio:
            _logger.warning("Realtime streaming returned no transcript; using batch fallback")
        elif self._frames and audio_duration_secs < self.MIN_COMMIT_AUDIO_SECS:
            _logger.warning(
                "Realtime streaming captured %.2fms of audio; skipping batch fallback",
                audio_duration_secs * 1000,
            )
        elif self._error:
            _logger.error(f"Realtime streaming failed without fallback audio: {self._error}")
        else:
            _logger.warning("Realtime streaming captured no audio")

        return StreamingTranscriptionResult(fallback_audio=fallback_audio, error=self._error)

    def cancel(self) -> None:
        """Stop streaming without committing or falling back to batch transcription."""
        self._cancel_requested = True
        self._stop_event.set()

        if self._audio_thread and self._audio_thread.is_alive():
            self._audio_thread.join(timeout=1.0)

        self._audio_queue.put(None)

        if self._websocket_thread and self._websocket_thread.is_alive():
            self._websocket_thread.join(timeout=1.0)

        with self._lock:
            self._streaming = False

        _logger.info("Realtime streaming transcription cancelled")

    def close(self) -> None:
        """Clean up audio resources."""
        self._stop_event.set()
        if self._owns_audio:
            try:
                self._audio.terminate()
            except Exception as e:
                _logger.debug(f"Error terminating realtime PyAudio instance: {e}")

    def _reset_state(self) -> None:
        """Reset per-session state before starting a stream."""
        self._audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._audio_started_event = threading.Event()
        self._frames = []
        self._transcript_parts = []
        self._last_transcript_event_at = None
        self._error = None
        self._cancel_requested = False
        self._chunks_delivered = False

    def _record_audio_loop(self) -> None:
        """Capture PCM16 microphone audio and feed the websocket sender."""
        stream = None
        start_time = time.time()
        try:
            stream = self._audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self._config.streaming_sample_rate,
                input=True,
                frames_per_buffer=self._config.audio_chunk_size,
                input_device_index=self._input_device_index,
            )
            self._audio_started_event.set()

            while not self._stop_event.is_set():
                if time.time() - start_time >= self._config.max_recording_duration:
                    _logger.info(
                        f"Maximum recording duration ({self._config.max_recording_duration}s) "
                        "reached"
                    )
                    break

                data = stream.read(self._config.audio_chunk_size, exception_on_overflow=False)
                self._frames.append(data)
                self._audio_queue.put(data)
        except Exception as e:
            self._error = f"Audio capture failed: {e}"
            _logger.error(self._error)
            self._audio_started_event.set()
        finally:
            if stream:
                try:
                    stream.stop_stream()
                    stream.close()
                except Exception as e:
                    _logger.debug(f"Error closing realtime audio stream: {e}")
            self._audio_queue.put(None)

    def _run_websocket_thread(self) -> None:
        """Run the websocket event loop in a background thread."""
        try:
            asyncio.run(self._run_websocket())
        except Exception as e:
            self._error = f"Realtime websocket failed: {e}"
            _logger.error(self._error)

    async def _run_websocket(self) -> None:
        """Open realtime websocket, stream audio, and collect final transcript."""
        headers = {
            "Authorization": f"Bearer {self._config.openai_api_key}",
        }

        async with websockets.connect(
            self.REALTIME_URL,
            additional_headers=headers,
            ping_interval=20,
        ) as websocket:
            await websocket.send(json.dumps(self._session_update_event()))
            sender = asyncio.create_task(self._send_audio(websocket))
            receiver = asyncio.create_task(self._receive_events(websocket))

            done, pending = await asyncio.wait(
                {sender, receiver},
                return_when=asyncio.FIRST_COMPLETED,
            )

            for task in done:
                task.result()

            if sender.done() and not receiver.done():
                try:
                    await self._wait_for_receiver_completion(receiver)
                except TimeoutError:
                    receiver.cancel()
                    _logger.warning("Timed out waiting for realtime transcription completion")

            for task in pending:
                if not task.done():
                    task.cancel()

    def _session_update_event(self) -> dict[str, typing.Any]:
        """Build session configuration for realtime transcription."""
        return {
            "type": "session.update",
            "session": {
                "type": "transcription",
                "audio": {
                    "input": {
                        "format": {
                            "type": "audio/pcm",
                            "rate": self._config.streaming_sample_rate,
                        },
                        "transcription": {
                            "model": self._config.streaming_transcription_model,
                            "language": "en",
                        },
                        "turn_detection": self._turn_detection_config(),
                    },
                },
            },
        }

    def _turn_detection_config(self) -> typing.Optional[dict[str, typing.Any]]:
        """Return realtime turn detection config, or None for manual commit on release."""
        if not self._config.streaming_turn_detection_enabled:
            return None

        return {
            "type": "server_vad",
            "threshold": 0.5,
            "prefix_padding_ms": 300,
            "silence_duration_ms": self._config.streaming_vad_silence_duration_ms,
        }

    async def _send_audio(self, websocket: typing.Any) -> None:
        """Send queued PCM audio chunks to the realtime websocket."""
        while True:
            chunk = await asyncio.to_thread(self._audio_queue.get)
            if chunk is None:
                break

            encoded_audio = base64.b64encode(chunk).decode("ascii")
            await websocket.send(
                json.dumps({"type": "input_audio_buffer.append", "audio": encoded_audio})
            )

        if self._captured_audio_duration_secs() < self.MIN_COMMIT_AUDIO_SECS:
            self._error = "Audio too short for realtime transcription"
            _logger.warning(self._error)
            await websocket.close()
            return

        if self._cancel_requested:
            await websocket.close()
            return

        if not self._config.streaming_turn_detection_enabled:
            await websocket.send(json.dumps({"type": "input_audio_buffer.commit"}))

    def _captured_audio_duration_secs(self) -> float:
        """Return captured PCM16 mono audio duration in seconds."""
        if not self._frames:
            return 0.0

        bytes_per_second = self._config.streaming_sample_rate * 2
        if bytes_per_second <= 0:
            return 0.0

        return sum(len(frame) for frame in self._frames) / bytes_per_second

    def _stop_join_timeout_secs(self) -> float:
        """Return websocket join timeout for stop."""
        if self._chunks_delivered and self._config.streaming_turn_detection_enabled:
            return self.WEBSOCKET_SHUTDOWN_GRACE_SECS

        return (
            self._config.streaming_completion_timeout_secs
            + self.WEBSOCKET_SHUTDOWN_GRACE_SECS
        )

    async def _receive_events(self, websocket: typing.Any) -> None:
        """Receive realtime transcription events."""
        async for message in websocket:
            event = json.loads(message)
            event_type = event.get("type", "")

            if event_type == "error":
                error = event.get("error", {})
                error_message = error.get("message", "unknown realtime transcription error")
                self._error = str(error_message)
                _logger.error(f"Realtime transcription error: {self._error}")
                return

            if (
                not self._config.streaming_turn_detection_enabled
                and event_type.endswith(".delta")
                and isinstance(event.get("delta"), str)
            ):
                self._transcript_parts.append(event["delta"])
                self._last_transcript_event_at = time.monotonic()
                continue

            if event_type.endswith(".completed"):
                transcript = event.get("transcript")
                if isinstance(transcript, str) and transcript.strip():
                    if self._config.streaming_turn_detection_enabled:
                        self._deliver_transcript_chunk(transcript)
                        continue

                    self._transcript_parts = [transcript]
                    self._last_transcript_event_at = time.monotonic()
                    return

    def _deliver_transcript_chunk(self, transcript: str) -> None:
        """Deliver one completed VAD transcript chunk."""
        text = transcript.strip()
        if not text:
            return

        self._chunks_delivered = True
        self._last_transcript_event_at = time.monotonic()
        if self._transcript_callback:
            self._transcript_callback(text)
        else:
            self._transcript_parts.append(text)

    async def _wait_for_receiver_completion(self, receiver: asyncio.Task[typing.Any]) -> None:
        """Wait for final realtime transcript without lingering after partial text arrives."""
        completion_deadline = time.monotonic() + self._config.streaming_completion_timeout_secs

        while not receiver.done():
            now = time.monotonic()
            deadline = completion_deadline
            if self._has_partial_transcript():
                last_event_at = self._last_transcript_event_at or now
                delta_idle_deadline = last_event_at + self._config.streaming_delta_idle_timeout_secs
                deadline = min(deadline, delta_idle_deadline)

            wait_secs = min(deadline - now, 0.25)
            if wait_secs <= 0:
                break

            try:
                await asyncio.wait_for(asyncio.shield(receiver), timeout=wait_secs)
            except TimeoutError:
                continue

        if receiver.done():
            receiver.result()
            return

        receiver.cancel()
        if self._has_partial_transcript():
            _logger.info("Using partial realtime transcript after delta idle timeout")
        else:
            _logger.warning("Timed out waiting for realtime transcription completion")

    def _has_partial_transcript(self) -> bool:
        """Return whether any realtime transcript text has arrived."""
        return any(part.strip() for part in self._transcript_parts)

    def _combined_transcript_text(self) -> str:
        """Return final transcript text from realtime parts."""
        if self._config.streaming_turn_detection_enabled:
            return " ".join(part.strip() for part in self._transcript_parts if part.strip())

        return "".join(self._transcript_parts).strip()

    def _frames_to_wav(self) -> bytes:
        """Convert captured PCM frames to WAV bytes for batch fallback."""
        wav_buffer = io.BytesIO()
        with wave.open(wav_buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(self._audio.get_sample_size(pyaudio.paInt16))
            wav_file.setframerate(self._config.streaming_sample_rate)
            wav_file.writeframes(b"".join(self._frames))

        wav_buffer.seek(0)
        return wav_buffer.read()

    @staticmethod
    def new(
        config: "ww.Config",
        transcript_callback: typing.Optional[typing.Callable[[str], None]] = None,
    ) -> "RealtimeStreamingTranscriptionClient":
        """Create realtime streaming transcription client."""
        return RealtimeStreamingTranscriptionClient(config, transcript_callback=transcript_callback)
