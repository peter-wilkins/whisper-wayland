"""Tests for the local file transcription API."""

from __future__ import annotations

import http.client
import json
import threading
from http import HTTPStatus
from http.server import ThreadingHTTPServer

import whisper_wayland as ww
from whisper_wayland.silero_vad import VadResult, VadSegment
from whisper_wayland.transcription_api import (
    TranscriptionApi,
    TranscriptionApiRequestHandler,
    UploadedAudio,
    _parse_multipart_audio,
)
from whisper_wayland.transcription_client.transcription_engine import (
    TimestampedTranscriptionResult,
    TranscriptionBackend,
    WordTimestamp,
)


class FakeTranscriptionClient:
    """Small fake matching the TranscriptionClient surface used by the API."""

    def __init__(self) -> None:
        """Create fake client."""
        self.last_transcription_backend = ww.TranscriptionBackendMetadata(
            provider="fake",
            processor_id="fake-model",
        )
        self.audio_data = b""
        self.language = ""

    def transcribe_audio(self, audio_data: bytes, language: str = "en") -> str:
        """Record request and return a transcript."""
        self.audio_data = audio_data
        self.language = language
        return "Hello from audio."

    def post_process_text(self, text: str) -> str:
        """Return deterministic post-processed text."""
        return f"Clean: {text}"

    def transcribe_audio_with_word_timestamps(
        self,
        audio_data: bytes,
        language: str = "en",
    ) -> TimestampedTranscriptionResult:
        """Record request and return deterministic timestamped transcript."""
        self.audio_data = audio_data
        self.language = language
        self.last_transcription_backend = ww.TranscriptionBackendMetadata(
            provider="openai",
            processor_id="whisper-1",
        )
        return TimestampedTranscriptionResult(
            text="Hello from audio.",
            words=[
                WordTimestamp(word="Hello", start=0.1, end=0.4),
                WordTimestamp(word="from", start=0.4, end=0.6),
                WordTimestamp(word="audio.", start=0.6, end=1.0),
            ],
            backend=TranscriptionBackend(provider="openai", processor_id="whisper-1"),
        )


class FakeSileroVad:
    """Fake Silero VAD preprocessor for API tests."""

    def __init__(self) -> None:
        """Create fake VAD."""
        self.audio_data = b""
        self.filename = ""

    def filter_audio(self, audio_data: bytes, filename: str | None = None) -> VadResult:
        """Return deterministic filtered audio."""
        self.audio_data = audio_data
        self.filename = filename or ""
        return VadResult(
            audio_data=b"speech-only",
            content_type="audio/ogg",
            filename_suffix=".silero.ogg",
            raw_duration_seconds=10.0,
            speech_duration_seconds=3.0,
            segments=[VadSegment(start_seconds=1.0, end_seconds=4.0)],
            threshold=0.5,
            model_path="fake.onnx",
        )


def test_transcription_api_transcribes_uploaded_audio() -> None:
    client = FakeTranscriptionClient()
    api = TranscriptionApi(client)  # type: ignore[arg-type]

    result = api.transcribe(
        UploadedAudio(
            data=b"audio",
            filename="ad.wav",
            content_type="audio/wav",
        ),
        language="en",
        post_process=True,
    )

    assert client.audio_data == b"audio"
    assert client.language == "en"
    assert result["schema"] == "whisper-wayland.transcription-api.v1"
    assert result["filename"] == "ad.wav"
    assert result["text"] == "Hello from audio."
    assert result["postProcessedText"] == "Clean: Hello from audio."
    assert result["backend"] == {"provider": "fake", "processorId": "fake-model"}


def test_transcription_api_can_preprocess_with_silero_vad() -> None:
    client = FakeTranscriptionClient()
    vad = FakeSileroVad()
    api = TranscriptionApi(client, silero_vad=vad)  # type: ignore[arg-type]

    result = api.transcribe(
        UploadedAudio(
            data=b"raw-audio",
            filename="long.wav",
            content_type="audio/wav",
        ),
        vad="silero",
    )

    assert vad.audio_data == b"raw-audio"
    assert vad.filename == "long.wav"
    assert client.audio_data == b"speech-only"
    assert result["transcribedFilename"] == "long.wav.silero.ogg"
    assert result["transcribedContentType"] == "audio/ogg"
    assert result["transcribedByteLength"] == len(b"speech-only")
    assert result["vad"] == {
        "enabled": True,
        "provider": "silero",
        "threshold": 0.5,
        "modelPath": "fake.onnx",
        "rawDurationSeconds": 10.0,
        "speechDurationSeconds": 3.0,
        "durationReductionPercent": 70.0,
        "segmentCount": 1,
        "segments": [{"start_seconds": 1.0, "end_seconds": 4.0}],
    }


def test_transcription_api_returns_word_timestamps() -> None:
    client = FakeTranscriptionClient()
    api = TranscriptionApi(client)  # type: ignore[arg-type]

    result = api.transcribe_with_word_timestamps(
        UploadedAudio(
            data=b"audio",
            filename="ad.wav",
            content_type="audio/wav",
        ),
        language="en",
    )

    assert client.audio_data == b"audio"
    assert result["text"] == "Hello from audio."
    assert result["words"] == [
        {"word": "Hello", "startSeconds": 0.1, "endSeconds": 0.4},
        {"word": "from", "startSeconds": 0.4, "endSeconds": 0.6},
        {"word": "audio.", "startSeconds": 0.6, "endSeconds": 1.0},
    ]
    assert result["backend"] == {"provider": "openai", "processorId": "whisper-1"}


def test_parse_multipart_audio_extracts_file_field() -> None:
    boundary = "test-boundary"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="voice.mp3"\r\n'
        "Content-Type: audio/mpeg\r\n"
        "\r\n"
        "abc123\r\n"
        f"--{boundary}--\r\n"
    ).encode()

    audio = _parse_multipart_audio(
        body,
        f"multipart/form-data; boundary={boundary}",
    )

    assert audio.data == b"abc123"
    assert audio.filename == "voice.mp3"
    assert audio.content_type == "audio/mpeg"


def test_handler_health_response() -> None:
    server = _start_test_server()

    try:
        status, payload = _request_json(server, "GET", "/health", b"")
        assert status == HTTPStatus.OK.value
        assert payload["ok"] is True
    finally:
        server.shutdown()


def test_handler_raw_audio_response() -> None:
    client = FakeTranscriptionClient()
    server = _start_test_server(client)

    try:
        status, payload = _request_json(
            server,
            "POST",
            "/v1/transcribe?language=es&postProcess=true",
            b"raw-audio",
            headers={
                "Content-Type": "audio/wav",
                "X-Filename": "clip.wav",
            },
        )
        assert status == HTTPStatus.OK.value
        assert payload["filename"] == "clip.wav"
        assert payload["byteLength"] == len(b"raw-audio")
        assert payload["language"] == "es"
        assert payload["postProcessedText"] == "Clean: Hello from audio."
    finally:
        server.shutdown()


def test_handler_word_timestamp_response() -> None:
    client = FakeTranscriptionClient()
    server = _start_test_server(client)

    try:
        status, payload = _request_json(
            server,
            "POST",
            "/v1/transcribe/words?language=en",
            b"raw-audio",
            headers={
                "Content-Type": "audio/wav",
                "X-Filename": "clip.wav",
            },
        )
        assert status == HTTPStatus.OK.value
        assert payload["filename"] == "clip.wav"
        assert payload["text"] == "Hello from audio."
        assert payload["words"][0] == {
            "word": "Hello",
            "startSeconds": 0.1,
            "endSeconds": 0.4,
        }
    finally:
        server.shutdown()


def _start_test_server(
    client: FakeTranscriptionClient | None = None,
) -> ThreadingHTTPServer:
    class Handler(TranscriptionApiRequestHandler):
        def log_message(self, format: str, *args: object) -> None:  # noqa: A002
            return

    Handler.api = TranscriptionApi(
        client or FakeTranscriptionClient(),  # type: ignore[arg-type]
        silero_vad=FakeSileroVad(),  # type: ignore[arg-type]
    )
    Handler.max_upload_bytes = 1024 * 1024
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def _request_json(
    server: ThreadingHTTPServer,
    method: str,
    path: str,
    body: bytes,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, object]]:
    connection = http.client.HTTPConnection(*server.server_address)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    payload = json.loads(response.read())
    connection.close()
    return response.status, payload
