"""In-process Slack Web API mock for slack-pack E2E tests.

Captures every ``/api/chat.*`` POST so tests can assert on what the
slack-pack adapter actually sent across the wire, and synthesizes
inbound Slack ``event_callback`` envelopes against an adapter callback
URL the test supplies.

The mock is deliberately the minimum surface needed to cover the
slack-pack pipeline. It is not a fidelity reimplementation of the
Slack Web API.

CSRF gate: when ``require_gc_request=True`` is passed at construction,
the mock returns 403 on any ``/api/chat.*`` POST that lacks the
``X-GC-Request: true`` header. This pins the fix from
gastownhall/gascity#1817 — the slack-pack adapter callback URL points
at gc's own ``/svc/<service>/publish`` proxy, which gates
private-service-proxy mutations on that header. Without the header,
delivery silently fails (FailureKind=auth) in production; this mock
makes that failure noisy in tests.
"""

from __future__ import annotations

import http.server
import json
import socketserver
import threading
import time
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass
class SlackCall:
    """A single Slack Web API call captured at the mock."""

    method: str
    channel: str
    thread_ts: str
    text: str
    blocks: Any
    idempotency_key: str
    gc_request: str
    raw: bytes
    at: float


class SlackMock:
    """HTTP server that stands in for the Slack Web API in tests."""

    def __init__(self, require_gc_request: bool = False) -> None:
        self.require_gc_request = require_gc_request
        self._calls: list[SlackCall] = []
        self._lock = threading.Lock()
        self._ts_counter = 0
        self._server = self._build_server()
        self._thread = threading.Thread(
            target=self._server.serve_forever, daemon=True, name="slack-mock"
        )
        self._thread.start()

    def _build_server(self) -> socketserver.TCPServer:
        outer = self

        class _Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self) -> None:  # noqa: N802 — stdlib API name
                outer._handle(self)

            def log_message(self, *args: Any, **kwargs: Any) -> None:
                # Silence access-log spam during tests.
                return

        return socketserver.TCPServer(("127.0.0.1", 0), _Handler)

    @property
    def url(self) -> str:
        """Base URL of the mock — point the slack-pack adapter's outbound HTTP client here."""
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def calls(self) -> list[SlackCall]:
        """Snapshot of every captured Slack API call so far."""
        with self._lock:
            return list(self._calls)

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()

    def _next_ts(self) -> str:
        """Deterministic message ts (seconds.microseconds), monotonic per instance."""
        with self._lock:
            self._ts_counter += 1
            n = self._ts_counter
        return f"17000000{n % 100:02d}.0001{n % 100:02d}"

    def _handle(self, req: http.server.BaseHTTPRequestHandler) -> None:
        gc_req = req.headers.get("X-GC-Request", "")
        if self.require_gc_request and gc_req != "true":
            req.send_response(403)
            req.end_headers()
            req.wfile.write(b"missing X-GC-Request: true")
            return

        length = int(req.headers.get("Content-Length", "0"))
        body = req.rfile.read(length) if length else b""

        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            req.send_response(400)
            req.end_headers()
            req.wfile.write(f"invalid json: {exc}".encode())
            return

        call = SlackCall(
            method=req.path,
            channel=parsed.get("channel", "") if isinstance(parsed, dict) else "",
            thread_ts=parsed.get("thread_ts", "") if isinstance(parsed, dict) else "",
            text=parsed.get("text", "") if isinstance(parsed, dict) else "",
            blocks=parsed.get("blocks") if isinstance(parsed, dict) else None,
            idempotency_key=parsed.get("idempotency_key", "") if isinstance(parsed, dict) else "",
            gc_request=gc_req,
            raw=body,
            at=time.time(),
        )
        with self._lock:
            self._calls.append(call)

        ts = self._next_ts()
        resp = json.dumps({"ok": True, "ts": ts, "channel": call.channel}).encode()
        req.send_response(200)
        req.send_header("Content-Type", "application/json")
        req.send_header("Content-Length", str(len(resp)))
        req.end_headers()
        req.wfile.write(resp)

    def emit_inbound_event(
        self,
        callback_url: str,
        channel: str,
        user: str,
        text: str,
        ts: str,
        thread_ts: str = "",
    ) -> None:
        """POST a synthetic Slack ``event_callback`` envelope at ``callback_url``.

        Models the Slack → adapter leg that real production traffic flows over.
        Raises RuntimeError if the callback returns a non-2xx status.
        """
        envelope = {
            "type": "event_callback",
            "team_id": "T0TESTWS",
            "event": {
                "type": "message",
                "channel": channel,
                "user": user,
                "text": text,
                "ts": ts,
                "thread_ts": thread_ts,
            },
        }
        body = json.dumps(envelope).encode()
        req = urllib.request.Request(
            callback_url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as resp:
            if resp.status >= 300:
                raise RuntimeError(
                    f"adapter rejected inbound event: status={resp.status}"
                )
