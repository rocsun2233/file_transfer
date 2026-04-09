from __future__ import annotations

import html
import json
import mimetypes
import secrets
from dataclasses import asdict, dataclass
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, quote, urlparse
from typing import Any

from .adapters import WebGateway
from .tasks import TaskManager
from .trust import TrustManager


class GuestAccessController:
    def __init__(self, trust_manager: TrustManager) -> None:
        self.trust_manager = trust_manager
        self._sessions: dict[str, dict[str, Any]] = {}

    def create_guest_session(self, guest_id: str) -> str:
        token = secrets.token_urlsafe(12)
        self._sessions[token] = {"guest_id": guest_id, "approved": False}
        return token

    def ensure_pending_guest_session(self, guest_id: str) -> str:
        for token, session in self._sessions.items():
            if session["guest_id"] == guest_id and not session["approved"]:
                return token
        return self.create_guest_session(guest_id)

    def approve(self, token: str) -> None:
        if token in self._sessions:
            self._sessions[token]["approved"] = True

    def can_transfer(self, token: str) -> bool:
        session = self._sessions.get(token)
        return bool(session and session["approved"])

    def has_session(self, token: str) -> bool:
        return token in self._sessions

    def list_pending_sessions(self) -> list[dict[str, Any]]:
        return [
            {"token": token, "guest_id": session["guest_id"], "approved": session["approved"]}
            for token, session in self._sessions.items()
            if not session["approved"]
        ]


@dataclass
class WebViewModel:
    can_upload: bool
    can_download: bool
    can_manage_trust: bool
    recent_tasks: list[dict[str, Any]]

    def to_json(self) -> str:
        return json.dumps(asdict(self))


@dataclass
class MobileWebViewModel:
    access_state: str
    can_upload: bool
    can_download: bool
    guest_token: str | None
    recent_tasks: list[dict[str, Any]]
    quick_actions: list[str]
    connection_hint: str
    support_note: str
    error_message: str | None

    @classmethod
    def from_state(
        cls,
        access_state: str,
        can_upload: bool,
        can_download: bool,
        guest_token: str | None,
        recent_tasks: list[dict[str, Any]],
        device_label: str,
        support_note: str,
        error_message: str | None,
    ) -> "MobileWebViewModel":
        actions = ["refresh"]
        if can_upload:
            actions.append("upload")
        if can_download:
            actions.append("download")
        if recent_tasks:
            actions.append("recent_tasks")
        return cls(
            access_state=access_state,
            can_upload=can_upload,
            can_download=can_download,
            guest_token=guest_token,
            recent_tasks=recent_tasks,
            quick_actions=actions,
            connection_hint=f"Connected to {device_label} via browser access.",
            support_note=support_note,
            error_message=error_message,
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self))


class LocalWebGatewayServer(WebGateway):
    def __init__(
        self,
        host: str,
        port: int,
        guest_access: GuestAccessController,
        task_manager: TaskManager,
        shared_dir: Path,
    ) -> None:
        self.host = host
        self.port = port
        self.guest_access = guest_access
        self.task_manager = task_manager
        self.shared_dir = Path(shared_dir)
        self.shared_dir.mkdir(parents=True, exist_ok=True)
        self.server = ThreadingHTTPServer((host, port), self._make_handler())
        self._thread: Thread | None = None
        self.start_background()

    def _make_handler(self) -> type[BaseHTTPRequestHandler]:
        guest_access = self.guest_access
        task_manager = self.task_manager
        shared_dir = self.shared_dir

        def resolve_token(headers: Any, parsed_url=None) -> str:
            if parsed_url is not None:
                params = parse_qs(parsed_url.query)
                query_token = params.get("token", [""])[0]
                if query_token:
                    return query_token
            token = headers.get("X-Guest-Token", "")
            if token:
                return token
            cookie_header = headers.get("Cookie", "")
            if not cookie_header:
                return ""
            cookies = SimpleCookie()
            cookies.load(cookie_header)
            return cookies.get("guest_token").value if "guest_token" in cookies else ""

        def list_download_items(token: str | None = None) -> list[dict[str, str]]:
            items: list[dict[str, str]] = []
            for path in sorted(shared_dir.rglob("*")):
                if not path.is_file():
                    continue
                relative = path.relative_to(shared_dir).as_posix()
                href = f"/download?name={quote(relative)}"
                if token:
                    href = f"{href}&token={quote(token)}"
                items.append({"name": relative, "href": href, "download_name": path.name})
            return items

        def content_disposition(filename: str) -> str:
            ascii_name = filename.encode("ascii", "ignore").decode("ascii") or "download"
            ascii_name = ascii_name.replace("\\", "_").replace('"', "_")
            return f'attachment; filename="{ascii_name}"; filename*=UTF-8\'\'{quote(filename)}'

        def render_mobile_page(model: MobileWebViewModel, downloads: list[dict[str, str]]) -> bytes:
            state_class = f"state-{html.escape(model.access_state)}"
            if downloads:
                download_list = "".join(
                    f'<li><a href="{html.escape(item["href"], quote=True)}" download="{html.escape(item["download_name"], quote=True)}">{html.escape(item["name"])}</a></li>'
                    for item in downloads
                )
            else:
                download_list = "<li>No files available yet.</li>"

            if model.recent_tasks:
                recent_tasks = "".join(
                    "<li>"
                    f"{html.escape(str(task.get('task_id', 'task')))}"
                    f" - {html.escape(str(task.get('state', 'unknown')))}"
                    "</li>"
                    for task in model.recent_tasks
                )
            else:
                recent_tasks = "<li>No recent tasks yet.</li>"

            upload_section = """
            <section class="panel">
              <h2>Upload Files</h2>
              <input id="file-input" type="file" multiple />
              <button id="upload-button" type="button">Upload Selected Files</button>
              <p id="upload-status" class="muted"></p>
            </section>
            """ if model.can_upload else ""

            refresh_label = "Refresh Access"
            error_block = (
                f'<p class="error">{html.escape(model.error_message)}</p>'
                if model.error_message
                else ""
            )
            html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Hybrid Transfer</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f4efe7;
      --card: #fffdf8;
      --ink: #1f2933;
      --muted: #5b6875;
      --accent: #1d6b57;
      --pending: #9a6700;
      --border: #d7cfc2;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "Noto Sans", sans-serif;
      background: linear-gradient(180deg, #f7f2ea 0%, #ede3d2 100%);
      color: var(--ink);
    }}
    main {{
      max-width: 720px;
      margin: 0 auto;
      padding: 16px;
    }}
    .hero, .panel {{
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: 18px;
      padding: 16px;
      margin-bottom: 14px;
      box-shadow: 0 10px 24px rgba(31, 41, 51, 0.08);
    }}
    .hero h1, .panel h2 {{ margin: 0 0 10px; }}
    .status-pill {{
      display: inline-block;
      padding: 6px 10px;
      border-radius: 999px;
      background: #e7f4ef;
      color: var(--accent);
      font-weight: 700;
      text-transform: capitalize;
    }}
    .state-pending .status-pill {{
      background: #fff1cf;
      color: var(--pending);
    }}
    .actions {{
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      margin-top: 12px;
    }}
    button, .action-link {{
      border: 0;
      border-radius: 12px;
      background: var(--accent);
      color: white;
      padding: 12px 16px;
      font-size: 15px;
      text-decoration: none;
    }}
    input[type=file] {{
      width: 100%;
      margin-bottom: 10px;
    }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    li {{
      margin-bottom: 8px;
      word-break: break-word;
    }}
    .muted {{
      color: var(--muted);
    }}
    .error {{
      color: #8a1c1c;
      font-weight: 600;
    }}
  </style>
</head>
<body>
  <main>
    <section class="hero {state_class}">
      <h1>Hybrid Transfer</h1>
      <p><span class="status-pill">{html.escape(model.access_state)}</span></p>
      <p>{html.escape(model.connection_hint)}</p>
      <p class="muted">{html.escape(model.support_note)}</p>
      {error_block}
      <div class="actions">
        <a class="action-link" href="/">{refresh_label}</a>
      </div>
    </section>
    {upload_section}
    <section class="panel">
      <h2>Available Downloads</h2>
      <ul>{download_list}</ul>
    </section>
    <section class="panel">
      <h2>Recent Tasks</h2>
      <ul>{recent_tasks}</ul>
    </section>
  </main>
  <script>
    const input = document.getElementById("file-input");
    const button = document.getElementById("upload-button");
    const status = document.getElementById("upload-status");
    if (button && input && status) {{
      button.addEventListener("click", async () => {{
        if (!input.files.length) {{
          status.textContent = "Choose at least one file first.";
          return;
        }}
        status.textContent = "Uploading...";
        for (const file of input.files) {{
          const response = await fetch(`/upload?name=${{encodeURIComponent(file.name)}}`, {{
            method: "POST",
            body: file,
            credentials: "same-origin"
          }});
          if (!response.ok) {{
            status.textContent = `Upload failed for ${{file.name}}`;
            return;
          }}
        }}
        status.textContent = "Upload complete. Refreshing...";
        window.location.reload();
      }});
    }}
  </script>
</body>
</html>
"""
            return html_doc.encode("utf-8")

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                resolved_token = resolve_token(self.headers, parsed)
                user_agent = self.headers.get("User-Agent", "")
                wants_mobile_json = "mobile=1" in parsed.query
                is_mobile = wants_mobile_json or "Android" in user_agent
                guest_id = self.client_address[0]
                token = resolved_token
                if parsed.path == "/" and (not token or not guest_access.has_session(token)):
                    token = guest_access.ensure_pending_guest_session(guest_id)
                allowed = guest_access.can_transfer(token)
                if parsed.path == "/download":
                    if not allowed:
                        self.send_error(403)
                        return
                    params = parse_qs(parsed.query)
                    filename = params.get("name", [""])[0]
                    target = (shared_dir / filename).resolve()
                    if shared_dir.resolve() not in target.parents and target != shared_dir.resolve():
                        self.send_error(400)
                        return
                    if not target.exists():
                        self.send_error(404)
                        return
                    body = target.read_bytes()
                    mime_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
                    self.send_response(200)
                    self.send_header("Content-Type", mime_type)
                    self.send_header("Content-Disposition", content_disposition(target.name))
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if parsed.path == "/" and not wants_mobile_json and (is_mobile or not resolved_token):
                    access_state = "authorized" if allowed else "pending"
                    mobile_model = MobileWebViewModel.from_state(
                        access_state=access_state,
                        can_upload=allowed,
                        can_download=allowed,
                        guest_token=token,
                        recent_tasks=task_manager.list_history()[-5:],
                        device_label="Hybrid Transfer",
                        support_note="Android currently uses browser access and is not a native client.",
                        error_message=None if allowed else "Waiting for approval or a valid access code.",
                    )
                    body = render_mobile_page(mobile_model, list_download_items(token) if allowed else [])
                    self.send_response(200)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    if token:
                        self.send_header("Set-Cookie", f"guest_token={token}; Path=/; SameSite=Lax")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                if is_mobile:
                    access_state = "authorized" if allowed else "pending"
                    mobile_model = MobileWebViewModel.from_state(
                        access_state=access_state,
                        can_upload=allowed,
                        can_download=allowed,
                        guest_token=token,
                        recent_tasks=task_manager.list_history()[-5:],
                        device_label="Hybrid Transfer",
                        support_note="Android currently uses browser access and is not a native client.",
                        error_message=None if allowed else "Waiting for approval or a valid access code.",
                    )
                    body = mobile_model.to_json().encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    if token:
                        self.send_header("Set-Cookie", f"guest_token={token}; Path=/; SameSite=Lax")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                model = WebViewModel(
                    can_upload=allowed,
                    can_download=allowed,
                    can_manage_trust=False,
                    recent_tasks=task_manager.list_history()[-10:],
                )
                body = model.to_json().encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                token = resolve_token(self.headers, parsed)
                if parsed.path != "/upload":
                    self.send_error(404)
                    return
                if not guest_access.can_transfer(token):
                    self.send_error(403)
                    return
                params = parse_qs(parsed.query)
                filename = params.get("name", [""])[0]
                if not filename:
                    self.send_error(400)
                    return
                target = (shared_dir / filename).resolve()
                if shared_dir.resolve() not in target.parents and target != shared_dir.resolve():
                    self.send_error(400)
                    return
                content_length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(content_length)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(body)
                self.send_response(201)
                self.send_header("Content-Length", "0")
                self.end_headers()

            def log_message(self, format: str, *args: Any) -> None:
                return

        return Handler

    def start_background(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = Thread(target=self.server.serve_forever, daemon=True)
        self._thread.start()

    def serve_forever(self) -> None:
        self.server.serve_forever()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()
