"""Local HTTP API for file-based transcription."""

from __future__ import annotations

import argparse
import json
import logging
import urllib.parse
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import whisper_wayland as ww
from whisper_wayland.silero_vad import SileroVadPreprocessor, audio_duration_seconds

_logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8788
DEFAULT_MAX_UPLOAD_BYTES = 100 * 1024 * 1024
API_VERSION = "whisper-wayland.transcription-api.v1"


@dataclass(frozen=True)
class UploadedAudio:
    """Audio payload extracted from an HTTP request."""

    data: bytes
    filename: str | None
    content_type: str


class TranscriptionApi:
    """Small local API wrapper around the existing transcription client."""

    def __init__(
        self,
        transcription_client: ww.TranscriptionClient,
        *,
        silero_vad: SileroVadPreprocessor | None = None,
        default_vad: str | None = None,
        auto_vad_min_duration_seconds: float | None = None,
    ) -> None:
        """Create an API wrapper."""
        self._transcription_client = transcription_client
        self._silero_vad = silero_vad or SileroVadPreprocessor()
        config = getattr(transcription_client, "config", None)
        self.default_vad = default_vad or getattr(config, "local_api_default_vad_mode", "none")
        self.auto_vad_min_duration_seconds = (
            auto_vad_min_duration_seconds
            if auto_vad_min_duration_seconds is not None
            else getattr(config, "transcription_vad_auto_min_duration_seconds", 60.0)
        )

    def transcribe(
        self,
        audio: UploadedAudio,
        *,
        language: str = "en",
        post_process: bool = False,
        vad: str = "none",
    ) -> dict[str, object]:
        """Transcribe uploaded audio and return a JSON-serializable payload."""
        transcription_audio, vad_metadata = self._prepare_audio(audio, vad)

        transcript = self._transcription_client.transcribe_audio(
            transcription_audio.data,
            language=language,
        )
        if transcript is None:
            transcript = ""

        processed_text = (
            self._transcription_client.post_process_text(transcript)
            if post_process and transcript.strip()
            else None
        )
        backend = self._transcription_client.last_transcription_backend
        return {
            "schema": API_VERSION,
            "filename": audio.filename,
            "contentType": audio.content_type,
            "byteLength": len(audio.data),
            "transcribedFilename": transcription_audio.filename,
            "transcribedContentType": transcription_audio.content_type,
            "transcribedByteLength": len(transcription_audio.data),
            "language": language,
            "vad": vad_metadata,
            "text": transcript,
            "postProcessedText": processed_text,
            "backend": (
                {
                    "provider": backend.provider,
                    "processorId": backend.processor_id,
                }
                if backend
                else None
            ),
        }

    def transcribe_with_word_timestamps(
        self,
        audio: UploadedAudio,
        *,
        language: str = "en",
        vad: str = "none",
    ) -> dict[str, object]:
        """Transcribe uploaded audio and return word-level timestamps."""
        transcription_audio, vad_metadata = self._prepare_audio(audio, vad)
        result = self._transcription_client.transcribe_audio_with_word_timestamps(
            transcription_audio.data,
            language=language,
        )
        text = result.text if result else ""
        words = result.words if result else []
        backend = self._transcription_client.last_transcription_backend
        return {
            "schema": API_VERSION,
            "filename": audio.filename,
            "contentType": audio.content_type,
            "byteLength": len(audio.data),
            "transcribedFilename": transcription_audio.filename,
            "transcribedContentType": transcription_audio.content_type,
            "transcribedByteLength": len(transcription_audio.data),
            "language": language,
            "vad": vad_metadata,
            "text": text,
            "words": [
                {
                    "word": word.word,
                    "startSeconds": word.start,
                    "endSeconds": word.end,
                }
                for word in words
            ],
            "backend": (
                {
                    "provider": backend.provider,
                    "processorId": backend.processor_id,
                }
                if backend
                else None
            ),
        }

    def _prepare_audio(
        self,
        audio: UploadedAudio,
        vad: str,
    ) -> tuple[UploadedAudio, dict[str, object]]:
        """Apply optional local preprocessing before transcription."""
        if vad == "auto":
            vad = self._resolve_auto_vad(audio)
        if vad == "none":
            return audio, {"enabled": False, "provider": None}
        if vad != "silero":
            raise ValueError("vad must be 'none', 'auto', or 'silero'")

        vad_result = self._silero_vad.filter_audio(audio.data, audio.filename)
        return (
            UploadedAudio(
                data=vad_result.audio_data,
                filename=_append_filename_suffix(audio.filename, vad_result.filename_suffix),
                content_type=vad_result.content_type,
            ),
            vad_result.metadata(),
        )

    def _resolve_auto_vad(self, audio: UploadedAudio) -> str:
        duration = audio_duration_seconds(audio.data, audio.filename)
        if duration is None:
            _logger.debug("Skipping auto VAD because audio duration is unknown")
            return "none"
        if duration >= self.auto_vad_min_duration_seconds:
            return "silero"
        return "none"


class TranscriptionApiRequestHandler(BaseHTTPRequestHandler):
    """HTTP handler for the local transcription API."""

    api: TranscriptionApi
    max_upload_bytes: int

    def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler hook
        """Handle health checks."""
        if self.path != "/health":
            self._write_error(HTTPStatus.NOT_FOUND, "Not found")
            return
        self._write_json(
            HTTPStatus.OK,
            {
                "ok": True,
                "schema": API_VERSION,
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler hook
        """Handle transcription requests."""
        path, _, query = self.path.partition("?")
        if path not in {"/v1/transcribe", "/v1/transcribe/words"}:
            self._write_error(HTTPStatus.NOT_FOUND, "Not found")
            return

        try:
            params = urllib.parse.parse_qs(query)
            language = params.get("language", ["en"])[0] or "en"
            post_process = _query_bool(params.get("postProcess", ["false"])[0])
            vad = params.get("vad", [self.api.default_vad])[0].strip().lower() or "none"
            audio = self._read_uploaded_audio()
            if path == "/v1/transcribe/words":
                result = self.api.transcribe_with_word_timestamps(
                    audio,
                    language=language,
                    vad=vad,
                )
            else:
                result = self.api.transcribe(
                    audio,
                    language=language,
                    post_process=post_process,
                    vad=vad,
                )
        except ValueError as e:
            self._write_error(HTTPStatus.BAD_REQUEST, str(e))
            return
        except ww.TranscriptionError as e:
            _logger.warning("Transcription API request failed: %s", e)
            self._write_error(HTTPStatus.BAD_GATEWAY, str(e))
            return

        self._write_json(HTTPStatus.OK, result)

    def _read_uploaded_audio(self) -> UploadedAudio:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            raise ValueError("Missing audio request body")
        if content_length > self.max_upload_bytes:
            raise ValueError(f"Audio upload exceeds {self.max_upload_bytes} bytes")

        content_type = self.headers.get("Content-Type", "application/octet-stream")
        body = self.rfile.read(content_length)
        if content_type.startswith("multipart/form-data"):
            return _parse_multipart_audio(body, content_type)

        return UploadedAudio(
            data=body,
            filename=self.headers.get("X-Filename"),
            content_type=content_type,
        )

    def _write_json(self, status: HTTPStatus, payload: dict[str, object]) -> None:
        body = json.dumps(payload).encode("utf-8") + b"\n"
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_error(self, status: HTTPStatus, message: str) -> None:
        self._write_json(status, {"ok": False, "error": message})


def serve(
    api: TranscriptionApi,
    *,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    max_upload_bytes: int = DEFAULT_MAX_UPLOAD_BYTES,
) -> None:
    """Serve the transcription API until interrupted."""

    class Handler(TranscriptionApiRequestHandler):
        pass

    Handler.api = api
    Handler.max_upload_bytes = max_upload_bytes
    server = ThreadingHTTPServer((host, port), Handler)
    _logger.info("Serving transcription API on http://%s:%s", host, port)
    server.serve_forever()


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint for the local transcription API."""
    parser = argparse.ArgumentParser(
        description="Serve the local WhisperWayland transcription API.",
    )
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--config")
    parser.add_argument("--max-upload-bytes", type=int, default=DEFAULT_MAX_UPLOAD_BYTES)
    args = parser.parse_args(argv)

    config = ww.Config(args.config)
    config.setup_logging()
    client = ww.TranscriptionClient(config)
    api = TranscriptionApi(client)
    serve(
        api,
        host=args.host,
        port=args.port,
        max_upload_bytes=args.max_upload_bytes,
    )
    return 0


def _query_bool(value: str) -> bool:
    return value.lower() in {"1", "true", "yes", "on"}


def _append_filename_suffix(filename: str | None, suffix: str) -> str | None:
    if not filename:
        return None
    return f"{filename}{suffix}"


def _parse_multipart_audio(body: bytes, content_type: str) -> UploadedAudio:
    boundary = _multipart_boundary(content_type)
    marker = b"--" + boundary
    for raw_part in body.split(marker):
        part = raw_part.strip()
        if not part or part == b"--":
            continue

        headers, separator, content = part.partition(b"\r\n\r\n")
        if not separator:
            continue
        content = content.removesuffix(b"\r\n").removesuffix(b"--")
        parsed_headers = _parse_part_headers(headers)
        disposition = parsed_headers.get("content-disposition", "")
        if 'name="file"' not in disposition:
            continue

        return UploadedAudio(
            data=content,
            filename=_disposition_value(disposition, "filename"),
            content_type=parsed_headers.get("content-type", "application/octet-stream"),
        )

    raise ValueError("multipart/form-data request must include a file field")


def _multipart_boundary(content_type: str) -> bytes:
    for raw_item in content_type.split(";"):
        item = raw_item.strip()
        if item.startswith("boundary="):
            return item.removeprefix("boundary=").strip('"').encode("utf-8")
    raise ValueError("multipart/form-data request is missing a boundary")


def _parse_part_headers(raw_headers: bytes) -> dict[str, str]:
    headers: dict[str, str] = {}
    for line in raw_headers.decode("utf-8", errors="replace").split("\r\n"):
        name, separator, value = line.partition(":")
        if separator:
            headers[name.strip().lower()] = value.strip()
    return headers


def _disposition_value(disposition: str, key: str) -> str | None:
    prefix = f'{key}="'
    for raw_item in disposition.split(";"):
        item = raw_item.strip()
        if item.startswith(prefix):
            return item.removeprefix(prefix).removesuffix('"')
    return None


if __name__ == "__main__":
    raise SystemExit(main())
