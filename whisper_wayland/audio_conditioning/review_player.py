"""Generate and serve a local audio review player for ranked replay runs."""

from __future__ import annotations

import argparse
import functools
import html
import http.server
import json
import os
import socketserver
import typing
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
INDEX_NAME = "review.html"
LABELS_NAME = "review-labels.json"


def main(argv: list[str] | None = None) -> int:
    """Generate a review player and optionally serve it over local HTTP."""
    parser = argparse.ArgumentParser(
        description="Build a local web player for transcription-plan audio candidates.",
    )
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--index-name", default=INDEX_NAME)
    parser.add_argument("--serve", action="store_true")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args(argv)

    index_path = write_review_player(args.run_dir, index_name=args.index_name)
    print(f"Wrote review player: {index_path}")
    if not args.serve:
        return 0

    url = f"http://{args.host}:{args.port}/{args.index_name}"
    print(f"Serving {args.run_dir} at {url}")
    serve_directory(args.run_dir, host=args.host, port=args.port)
    return 0


def write_review_player(run_dir: Path, *, index_name: str = INDEX_NAME) -> Path:
    """Write a static audio review page into a replay run directory."""
    run_dir = run_dir.expanduser().resolve()
    payload = _load_run_payload(run_dir)
    index_path = run_dir / index_name
    index_path.write_text(_render_html(payload), encoding="utf-8")
    return index_path


def serve_directory(directory: Path, *, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Serve a directory with Python's local HTTP server."""
    resolved_directory = directory.expanduser().resolve()
    handler = functools.partial(
        ReviewRequestHandler,
        directory=str(resolved_directory),
    )
    with socketserver.TCPServer((host, port), handler) as server:
        server.serve_forever()


class ReviewRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Static file server plus a tiny local-only label endpoint."""

    def do_POST(self) -> None:  # noqa: N802 - http.server hook name
        """Persist clip review labels beside the run JSON."""
        if self.path != "/labels":
            self.send_error(404, "Unknown endpoint")
            return

        try:
            payload = self._read_json_body()
            saved = _save_review_label(Path(self.directory), payload)
        except (ValueError, OSError, json.JSONDecodeError) as e:
            self.send_error(400, str(e))
            return

        body = json.dumps({"ok": True, "labelCount": len(saved["labels"])}) + "\n"
        encoded = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _read_json_body(self) -> dict[str, typing.Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("Missing JSON request body")
        return json.loads(self.rfile.read(length).decode("utf-8"))


def _load_run_payload(run_dir: Path) -> dict[str, typing.Any]:
    run_json = run_dir / "run.json"
    if not run_json.exists():
        raise FileNotFoundError(f"Missing replay run JSON: {run_json}")
    payload = json.loads(run_json.read_text(encoding="utf-8"))
    if "transcriptionPlan" not in payload:
        raise ValueError("run.json does not contain a transcriptionPlan")
    return payload


def _save_review_label(
    run_dir: Path,
    payload: dict[str, typing.Any],
) -> dict[str, typing.Any]:
    relative_path = str(payload.get("relativePath", "")).strip()
    label = str(payload.get("label", "")).strip()
    if label not in {"speech", "partial", "noise"}:
        raise ValueError("label must be speech, partial, or noise")
    if not relative_path or os.path.isabs(relative_path) or ".." in Path(relative_path).parts:
        raise ValueError("relativePath must be a safe relative path")

    labels_path = run_dir / LABELS_NAME
    if labels_path.exists():
        labels_payload = json.loads(labels_path.read_text(encoding="utf-8"))
    else:
        labels_payload = {
            "schema": "whisper_wayland.audio_conditioning.review_labels.v1",
            "labels": [],
        }

    labels = [
        item
        for item in labels_payload.get("labels", [])
        if item.get("relativePath") != relative_path
    ]
    labels.append(
        {
            "relativePath": relative_path,
            "label": label,
            "speechRank": payload.get("speechRank"),
            "speechScore": payload.get("speechScore"),
            "sourceStartSeconds": payload.get("sourceStartSeconds"),
            "sourceEndSeconds": payload.get("sourceEndSeconds"),
        }
    )
    labels_payload["labels"] = sorted(labels, key=lambda item: str(item["relativePath"]))
    tmp_path = labels_path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(labels_payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(labels_path)
    return labels_payload


def _render_html(payload: dict[str, typing.Any]) -> str:
    plan = payload["transcriptionPlan"]
    source = payload["source"]
    segments = list(plan.get("segments", []))
    cards = "\n".join(
        _render_segment_card(segment, index) for index, segment in enumerate(segments, start=1)
    )
    if not cards:
        cards = '<p class="empty">No selected transcription candidates.</p>'
    selected_duration = float(plan.get("selectedDurationSeconds", 0.0))
    duration_reduction = float(plan.get("durationReductionPercent", 0.0))
    upload_reduction = float(plan.get("uploadSizeReductionPercent", 0.0))

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>WhisperWayland Audio Review</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --text: #18212f;
      --muted: #586274;
      --line: #d8dde6;
      --accent: #1f6feb;
      --accent-dark: #164fa8;
      --ok: #147d64;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }}
    main {{
      max-width: 1120px;
      margin: 0 auto;
      padding: 24px;
    }}
    header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 12px;
      padding-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0;
      font-size: 24px;
      line-height: 1.2;
      font-weight: 720;
      letter-spacing: 0;
    }}
    .source {{
      margin: 0;
      color: var(--muted);
      overflow-wrap: anywhere;
      font-size: 14px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 10px;
      margin: 18px 0;
    }}
    .stat {{
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 12px;
    }}
    .stat span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 4px;
    }}
    .stat strong {{
      font-size: 18px;
      line-height: 1.2;
    }}
    .list {{
      display: grid;
      gap: 12px;
    }}
    .clip {{
      display: grid;
      grid-template-columns: 96px minmax(0, 1fr) minmax(260px, 360px);
      gap: 14px;
      align-items: center;
      border: 1px solid var(--line);
      background: var(--panel);
      border-radius: 8px;
      padding: 14px;
    }}
    .rank {{
      font-size: 13px;
      color: var(--muted);
    }}
    .rank strong {{
      display: block;
      color: var(--text);
      font-size: 26px;
    }}
    .meta {{
      min-width: 0;
    }}
    .meta h2 {{
      margin: 0 0 6px;
      font-size: 16px;
      line-height: 1.25;
      letter-spacing: 0;
    }}
    .meta p {{
      margin: 0;
      color: var(--muted);
      font-size: 13px;
      overflow-wrap: anywhere;
    }}
    .controls {{
      display: grid;
      grid-template-columns: 82px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
    }}
    .labels {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      grid-column: 1 / -1;
    }}
    button {{
      min-height: 40px;
      border: 0;
      border-radius: 8px;
      background: var(--accent);
      color: white;
      font: inherit;
      font-weight: 650;
      cursor: pointer;
    }}
    button:hover {{ background: var(--accent-dark); }}
    button.playing {{ background: var(--ok); }}
    button.label {{
      min-height: 34px;
      padding: 0 12px;
      background: #e8edf5;
      color: var(--text);
      border: 1px solid var(--line);
      font-size: 13px;
    }}
    button.label:hover {{ background: #dce4f0; }}
    button.label.selected {{
      background: var(--ok);
      border-color: var(--ok);
      color: white;
    }}
    audio {{
      width: 100%;
      min-width: 0;
    }}
    .empty {{
      color: var(--muted);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }}
    @media (max-width: 760px) {{
      main {{ padding: 16px; }}
      .clip {{
        grid-template-columns: minmax(0, 1fr);
      }}
      .controls {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>WhisperWayland Audio Review</h1>
      <p class="source">{html.escape(str(source.get("path", "unknown source")))}</p>
    </header>
    <section class="stats" aria-label="Transcription plan stats">
      {_render_stat("Selected clips", plan.get("selectedSegmentCount", 0))}
      {_render_stat("Selected duration", f"{selected_duration:.3f}s")}
      {_render_stat("Duration saved", f"{duration_reduction:.1f}%")}
      {_render_stat("Upload saved", f"{upload_reduction:.1f}%")}
    </section>
    <section class="list" aria-label="Selected audio windows">
      {cards}
    </section>
  </main>
  <script>
    const audios = Array.from(document.querySelectorAll("audio"));
    const buttons = Array.from(document.querySelectorAll("button[data-target]"));
    const labelButtons = Array.from(document.querySelectorAll("button[data-label]"));

    function resetButtons() {{
      buttons.forEach((button) => {{
        button.textContent = "Play";
        button.classList.remove("playing");
      }});
    }}

    buttons.forEach((button) => {{
      button.addEventListener("click", () => {{
        const audio = document.getElementById(button.dataset.target);
        const shouldPlay = audio.paused;
        audios.forEach((item) => {{
          if (item !== audio) {{
            item.pause();
            item.currentTime = 0;
          }}
        }});
        resetButtons();
        if (shouldPlay) {{
          audio.play();
          button.textContent = "Pause";
          button.classList.add("playing");
        }} else {{
          audio.pause();
        }}
      }});
    }});

    audios.forEach((audio) => {{
      audio.addEventListener("ended", resetButtons);
      audio.addEventListener("pause", () => {{
        if (audios.every((item) => item.paused)) resetButtons();
      }});
    }});

    labelButtons.forEach((button) => {{
      button.addEventListener("click", async () => {{
        const clip = button.closest(".clip");
        const payload = {{
          relativePath: clip.dataset.relativePath,
          speechRank: Number(clip.dataset.speechRank),
          speechScore: Number(clip.dataset.speechScore),
          sourceStartSeconds: Number(clip.dataset.sourceStart),
          sourceEndSeconds: Number(clip.dataset.sourceEnd),
          label: button.dataset.label,
        }};
        const response = await fetch("/labels", {{
          method: "POST",
          headers: {{"Content-Type": "application/json"}},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) {{
          button.textContent = "Failed";
          return;
        }}
        clip.querySelectorAll("button[data-label]").forEach((item) => {{
          item.classList.toggle("selected", item === button);
        }});
      }});
    }});
  </script>
</body>
</html>
"""


def _render_stat(label: str, value: typing.Any) -> str:
    return (
        '<div class="stat">'
        f"<span>{html.escape(label)}</span>"
        f"<strong>{html.escape(str(value))}</strong>"
        "</div>"
    )


def _render_segment_card(segment: dict[str, typing.Any], index: int) -> str:
    audio_id = f"clip-{index}"
    relative_path = html.escape(str(segment["relative_path"]))
    start = float(segment["source_start_seconds"])
    end = float(segment["source_end_seconds"])
    duration = max(0.0, end - start)
    rank = segment.get("speech_rank", index)
    score = float(segment.get("speech_score", 0.0))
    reason = html.escape(str(segment.get("speech_features", {}).get("reason", "candidate")))
    play_label = html.escape(str(rank))
    return f"""<article
  class="clip"
  data-relative-path="{relative_path}"
  data-speech-rank="{html.escape(str(rank))}"
  data-speech-score="{score:.3f}"
  data-source-start="{start:.3f}"
  data-source-end="{end:.3f}"
>
  <div class="rank">Rank <strong>{html.escape(str(rank))}</strong></div>
  <div class="meta">
    <h2>{start:.3f}s to {end:.3f}s</h2>
    <p>Score {score:.3f} · Duration {duration:.3f}s · {reason}</p>
    <p>{relative_path}</p>
  </div>
  <div class="controls">
    <button type="button" data-target="{audio_id}" aria-label="Play clip rank {play_label}">
      Play
    </button>
    <audio id="{audio_id}" controls preload="metadata" src="{relative_path}"></audio>
    <div class="labels" aria-label="Clip labels">
      <button class="label" type="button" data-label="speech">Speech</button>
      <button class="label" type="button" data-label="partial">Partial</button>
      <button class="label" type="button" data-label="noise">Noise</button>
    </div>
  </div>
</article>"""


if __name__ == "__main__":
    raise SystemExit(main())
