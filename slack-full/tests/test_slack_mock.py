"""Self-tests for ``slack_mock.SlackMock``.

These pin the mock's contract so a later refactor that breaks capture
semantics fails here — where the failure is unambiguous — instead of in
higher-level E2E tests where the failure could look like a slack-pack
bug.

The mock itself is intended to be reused by future end-to-end tests
that exercise the full pipeline (slack-pack script → gc /extmsg/* →
adapter callback → Slack publish). This file deliberately does not
exercise that pipeline; it tests only the mock's own capture, CSRF
gate, and inbound-event-synthesis behavior.
"""

from __future__ import annotations

import http.server
import json
import pathlib
import socketserver
import sys
import threading
import urllib.error
import urllib.request

import pytest

# Make slack_mock importable without depending on conftest setup.
TESTS_DIR = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS_DIR))

from slack_mock import SlackMock  # type: ignore  # noqa: E402


@pytest.fixture
def mock() -> "SlackMock":
    m = SlackMock()
    yield m
    m.close()


def test_captures_post_message(mock: SlackMock) -> None:
    """Happy-path: chat.postMessage POST is captured with channel, text, thread_ts, idempotency_key, X-GC-Request."""
    body = json.dumps({
        "channel": "C123",
        "text": "hello",
        "thread_ts": "1700000000.000100",
        "idempotency_key": "k-1",
    }).encode()
    req = urllib.request.Request(
        f"{mock.url}/api/chat.postMessage",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", "X-GC-Request": "true"},
    )
    with urllib.request.urlopen(req, timeout=2) as resp:
        assert resp.status == 200
        decoded = json.loads(resp.read())

    assert decoded["ok"] is True
    assert decoded["ts"], f"expected non-empty ts in response, got {decoded!r}"

    calls = mock.calls()
    assert len(calls) == 1
    c = calls[0]
    assert c.channel == "C123"
    assert c.text == "hello"
    assert c.thread_ts == "1700000000.000100"
    assert c.idempotency_key == "k-1"
    assert c.gc_request == "true"


def test_csrf_gate_rejects_missing_header() -> None:
    """Pins the gastownhall/gascity#1817 regression.

    When ``require_gc_request=True`` is set, /api/chat.* POSTs missing
    X-GC-Request: true are rejected with 403 and not recorded as a
    captured call. A regression that drops the header in
    HTTPAdapter.Publish would silently fail delivery in production;
    this gate makes that failure loud in tests.
    """
    mock = SlackMock(require_gc_request=True)
    try:
        body = json.dumps({"channel": "C1", "text": "x"}).encode()
        req = urllib.request.Request(
            f"{mock.url}/api/chat.postMessage",
            data=body,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(req, timeout=2)
        assert exc_info.value.code == 403
        assert mock.calls() == [], (
            f"CSRF-gated request should not have been recorded, got {mock.calls()!r}"
        )
    finally:
        mock.close()


def test_emit_inbound_event(mock: SlackMock) -> None:
    """Mock can synthesize an inbound Slack event and POST it at a callback URL.

    This is the Slack → adapter leg that higher-level E2E tests use.
    """
    received: list[tuple[bytes, dict[str, str]]] = []

    class _CallbackHandler(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 — stdlib API name
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length else b""
            received.append((body, dict(self.headers)))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args: object, **kwargs: object) -> None:
            return

    callback = socketserver.TCPServer(("127.0.0.1", 0), _CallbackHandler)
    callback_thread = threading.Thread(
        target=callback.serve_forever, daemon=True, name="callback-mock"
    )
    callback_thread.start()
    host, port = callback.server_address
    callback_url = f"http://{host}:{port}/inbound"

    try:
        mock.emit_inbound_event(
            callback_url,
            channel="C1",
            user="U1",
            text="hi",
            ts="1700000000.000200",
        )
        assert len(received) == 1, f"expected callback to fire exactly once, got {len(received)}"
        body, headers = received[0]
        envelope = json.loads(body)
        assert envelope["type"] == "event_callback"
        ev = envelope["event"]
        assert ev["channel"] == "C1"
        assert ev["user"] == "U1"
        assert ev["text"] == "hi"
        assert headers.get("Content-Type") == "application/json"
    finally:
        callback.shutdown()
        callback.server_close()
