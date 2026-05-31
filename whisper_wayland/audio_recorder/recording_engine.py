"""Whisper Wayland - Recording Engine

Core audio recording engine with threading and stream management.
"""

import logging
import math
import threading
import time
import typing
from collections import deque

import pyaudio

import whisper_wayland as ww

_logger = logging.getLogger(__name__)

STREAM_READY_TIMEOUT_SECS = 1.0
THREAD_JOIN_TIMEOUT_SECS = 5.0
READER_RETRY_SLEEP_SECS = 0.05
READER_MAX_CONSECUTIVE_ERRORS = 3
MS_PER_SECOND = 1000


class RecordingEngineError(Exception):
    """Raised when recording engine operations fail."""

    pass


class RecordingEngine:
    """Core audio recording engine with threading support."""

    def __init__(
        self,
        audio: pyaudio.PyAudio,
        config: "ww.Config",
        input_device_index: typing.Optional[int] = None,
    ) -> None:
        """Initialize recording engine.

        Args:
            audio: PyAudio instance
            config: Configuration instance
            input_device_index: Input device index, or None for system default
        """
        self._audio = audio
        self._config = config
        self._input_device_index = input_device_index
        self._effective_sample_rate = self._resolve_sample_rate(audio, input_device_index, config)
        self._stream: typing.Optional[pyaudio.Stream] = None
        self._recording = False
        self._recording_started_at = 0.0
        self._max_duration_logged = False
        self._reader_thread: typing.Optional[threading.Thread] = None
        self._reader_stop_event = threading.Event()
        self._reader_started_event = threading.Event()
        self._reader_error_count = 0
        self._preroll_frames: deque[bytes] = deque(maxlen=self._preroll_chunk_count())
        self._recording_frames: typing.Optional[list[bytes]] = None
        self._lock = threading.Lock()

    def prepare_stream(self) -> None:
        """Open and start the input stream ahead of the first hotkey press."""
        with self._lock:
            if self._reader_thread and self._reader_thread.is_alive():
                return

            started_at = time.monotonic()
            try:
                self._prepare_stream_locked()
                elapsed_ms = (time.monotonic() - started_at) * MS_PER_SECOND
                _logger.info(
                    "Audio input stream warmed in %.0fms with %.1fs pre-roll",
                    elapsed_ms,
                    self._config.audio_preroll_seconds,
                )
            except Exception as e:
                self._close_stream_locked()
                _logger.warning("Could not pre-open audio input stream: %s", e)

    def start_recording(self) -> None:
        """Start audio recording in a separate thread.

        Raises:
            RecordingEngineError: If recording cannot be started
        """
        with self._lock:
            if self._recording:
                _logger.warning("Recording already in progress")
                return

            try:
                started_at = time.monotonic()
                if not self._reader_thread or not self._reader_thread.is_alive():
                    self._prepare_stream_locked()

                self._recording = True
                self._recording_started_at = time.monotonic()
                self._max_duration_logged = False
                self._recording_frames = list(self._preroll_frames)
                preroll_count = len(self._recording_frames)

                elapsed_ms = (time.monotonic() - started_at) * MS_PER_SECOND
                _logger.info(
                    "Audio recording started in %.0fms with %d pre-roll chunk(s)",
                    elapsed_ms,
                    preroll_count,
                )
            except Exception as e:
                self._recording = False
                _logger.error(f"Failed to start recording: {e}")
                raise RecordingEngineError(f"Failed to start recording: {e}") from e

    def stop_recording(self) -> typing.Optional[bytes]:
        """Stop audio recording and return recorded data.

        Returns:
            Recorded audio data as WAV bytes, or None if no data recorded

        Raises:
            RecordingEngineError: If stopping recording fails
        """
        try:
            with self._lock:
                frames = self._recording_frames
                if not self._recording and frames is None:
                    _logger.warning("No recording in progress")
                    return None

                self._recording = False
                self._recording_frames = None
                _logger.debug("Stopping audio recording...")

            audio_data = self._frames_to_wav(frames or [])

            if audio_data:
                _logger.info(f"Audio recording stopped, captured {len(audio_data)} bytes")
            else:
                _logger.warning("No audio data captured")

            return audio_data

        except Exception as e:
            _logger.error(f"Failed to stop recording: {e}")
            raise RecordingEngineError(f"Failed to stop recording: {e}") from e

    def _reader_loop(self) -> None:
        """Continuously keep a tiny local pre-roll buffer warm."""
        self._reader_started_event.set()

        while not self._reader_stop_event.is_set():
            stream = self._stream
            if not stream:
                break

            try:
                data = stream.read(self._config.audio_chunk_size, exception_on_overflow=False)
            except Exception as e:
                if self._reader_stop_event.is_set():
                    break
                self._reader_error_count += 1
                _logger.warning(
                    "Error reading audio data (%d/%d): %s",
                    self._reader_error_count,
                    READER_MAX_CONSECUTIVE_ERRORS,
                    e,
                )
                if self._reader_error_count >= READER_MAX_CONSECUTIVE_ERRORS:
                    _logger.warning("Audio reader stream failed; will reopen on next recording")
                    break
                time.sleep(READER_RETRY_SLEEP_SECS)
                continue

            if not isinstance(data, bytes):
                time.sleep(READER_RETRY_SLEEP_SECS)
                continue

            self._reader_error_count = 0
            self._store_frame(data)

    def _store_frame(self, data: bytes) -> None:
        with self._lock:
            if self._recording and self._recording_frames is not None:
                if self._within_max_duration_locked():
                    self._recording_frames.append(data)
                return

            if self._preroll_frames.maxlen:
                self._preroll_frames.append(data)

    def _within_max_duration_locked(self) -> bool:
        elapsed = time.monotonic() - self._recording_started_at
        max_duration = self._config.max_recording_duration
        if elapsed < max_duration:
            return True

        if not self._max_duration_logged:
            _logger.info(f"Maximum recording duration ({max_duration}s) reached")
            self._max_duration_logged = True
        return False

    def _frames_to_wav(self, frames: list[bytes]) -> typing.Optional[bytes]:
        if not frames:
            return None

        try:
            from whisper_wayland.audio_recorder.wav_converter import WavConverter

            wav_converter = WavConverter.new(self._audio, self._config)
            audio_data = wav_converter.frames_to_wav(frames, self._effective_sample_rate)
            _logger.debug(f"Converted {len(frames)} frames to WAV format")
            return audio_data
        except Exception as e:
            _logger.error(f"Failed to convert audio frames to WAV: {e}")
            return None

    def _prepare_stream_locked(self) -> None:
        self._close_stream_locked()
        self._stream = self._open_stream(start=True)
        self._reader_stop_event = threading.Event()
        self._reader_started_event = threading.Event()
        self._reader_error_count = 0
        self._preroll_frames = deque(maxlen=self._preroll_chunk_count())
        self._reader_thread = threading.Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

        if not self._reader_started_event.wait(timeout=STREAM_READY_TIMEOUT_SECS):
            raise RecordingEngineError("Audio reader did not report ready within 1s")

    def _preroll_chunk_count(self) -> int:
        preroll_seconds = self._config.audio_preroll_seconds
        if preroll_seconds <= 0:
            return 0
        return max(
            1,
            math.ceil(
                (preroll_seconds * self._effective_sample_rate) / self._config.audio_chunk_size
            ),
        )

    def _open_stream(self, start: bool) -> pyaudio.Stream:
        """Open a PyAudio stream without doing the slow setup on hotkey press."""
        return self._audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self._effective_sample_rate,
            input=True,
            frames_per_buffer=self._config.audio_chunk_size,
            input_device_index=self._input_device_index,
            start=start,
        )

    def _close_stream_locked(self) -> None:
        """Close audio stream resources."""
        reader_thread = self._reader_thread
        stream = self._stream
        self._reader_thread = None
        self._stream = None
        self._reader_stop_event.set()

        if stream:
            try:
                stream.stop_stream()
            except Exception:
                pass

        if reader_thread and reader_thread.is_alive():
            self._lock.release()
            try:
                reader_thread.join(timeout=THREAD_JOIN_TIMEOUT_SECS)
            finally:
                self._lock.acquire()

        if stream:
            try:
                stream.close()
                _logger.debug("Audio stream closed")
            except Exception as e:
                _logger.error(f"Error closing audio stream: {e}")

    def close(self) -> None:
        """Release stream resources."""
        with self._lock:
            self._recording = False
            self._recording_frames = None
            self._close_stream_locked()

    def is_recording(self) -> bool:
        """Check if recording is currently in progress.

        Returns:
            True if recording is active, False otherwise
        """
        with self._lock:
            return self._recording

    @property
    def input_device_index(self) -> typing.Optional[int]:
        """Input device index used by this engine, or None for system default."""
        return self._input_device_index

    @staticmethod
    def _resolve_sample_rate(
        audio: pyaudio.PyAudio,
        input_device_index: typing.Optional[int],
        config: "ww.Config",
    ) -> int:
        """Resolve the effective sample rate for the chosen input device.

        Uses the device's native sample rate when a specific device is selected,
        falling back to the configured rate otherwise.
        """
        if input_device_index is not None:
            try:
                info = audio.get_device_info_by_index(input_device_index)
                native_rate = int(info["defaultSampleRate"])
                _logger.debug(f"Using device native sample rate: {native_rate} Hz")
                return native_rate
            except Exception as e:
                _logger.warning(f"Could not read device sample rate, using config value: {e}")
        return config.audio_sample_rate

    @staticmethod
    def new(
        audio: pyaudio.PyAudio,
        config: "ww.Config",
        input_device_index: typing.Optional[int] = None,
    ) -> "RecordingEngine":
        """Create recording engine instance.

        Args:
            audio: PyAudio instance
            config: Configuration instance
            input_device_index: Input device index, or None for system default

        Returns:
            RecordingEngine instance
        """
        return RecordingEngine(audio, config, input_device_index)
