"""Tests for ``slack_intake_common._request`` at the real socket boundary.

Every other slack-pack test stubs ``_request`` out, which is right for
them and is exactly why the defect on dr-3lhmr survived: the escaping
exception is raised by the socket layer that the stubs replace.

So these tests speak HTTP to a real listener over a real loopback
socket. The helpers in this module deliberately build the failure at
the transport, not by raising a chosen exception, because the whole
question is which exception the transport actually produces and
whether ``_request`` converts it.
"""

from __future__ import annotations

import pathlib
import socket
import sys
import threading
import time

import pytest

PACK_DIR = pathlib.Path(__file__).resolve().parent.parent
SCRIPTS_DIR = PACK_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("GC_CITY_NAME", "test-city")
    monkeypatch.setenv("GC_CITY_PATH", str(tmp_path))
    monkeypatch.delenv("GC_SLACK_ADAPTER_ENV", raising=False)


def _import_common():
    sys.modules.pop("slack_intake_common", None)
    import slack_intake_common  # type: ignore
    return slack_intake_common


def _drain_request(conn: socket.socket) -> bool:
    """Read the request head through its terminating blank line.

    A single recv() can return a partial request. The client is then still
    writing when the listener answers or resets, which moves the failure
    from the response read to the request send -- a different exception
    class, and on unfixed code a different result. Returns False if the
    peer went away first.
    """
    buf = b""
    conn.settimeout(5.0)
    while b"\r\n\r\n" not in buf:
        try:
            chunk = conn.recv(4096)
        except OSError:
            return False
        if not chunk:
            return False
        buf += chunk
    conn.settimeout(None)
    return True


class _Listener:
    """A loopback listener that misbehaves in one chosen way.

    ``mode`` is one of:
      stall_body        send a 200 and a Content-Length, then send no body
      stall_header      accept the connection and send nothing at all
      reset             send a 200, a Content-Length and a short body, then RST
      short_body        send a 200 and a Content-Length, then a SHORTER body
                        and a clean close
      bad_status        answer with something that is not a status line
      error_short_body  send a 500 and a Content-Length, then a SHORTER body
                        and a clean close

    Every mode drains the request headers through the blank line before it
    answers. Answering or resetting earlier lets the failure land in the
    client's send instead of its read, and urllib reports those two as
    different exception types -- so the test would pass or fail by timing
    on unfixed code and prove nothing.
    """

    def __init__(self, mode: str) -> None:
        self.mode = mode
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.listen(1)
        self.port = self.sock.getsockname()[1]
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        try:
            conn, _ = self.sock.accept()
        except OSError:
            return
        with conn:
            if not _drain_request(conn):
                return
            if self.mode == "reset":
                try:
                    conn.sendall(b"HTTP/1.1 200 OK\r\n"
                                 b"Content-Type: application/json\r\n"
                                 b"Content-Length: 4096\r\n\r\n"
                                 b'{"items":')
                except OSError:
                    return
                conn.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER,
                                b"\x01\x00\x00\x00\x00\x00\x00\x00")
                return
            if self.mode in ("short_body", "error_short_body"):
                status = (b"HTTP/1.1 200 OK\r\n" if self.mode == "short_body"
                          else b"HTTP/1.1 500 Internal Server Error\r\n")
                try:
                    conn.sendall(status +
                                 b"Content-Type: application/json\r\n"
                                 b"Content-Length: 4096\r\n\r\n"
                                 b'{"items":')
                except OSError:
                    return
                return   # clean close: FIN, not RST, so the client sees a
                         # body shorter than the Content-Length it was promised
            if self.mode == "bad_status":
                try:
                    conn.sendall(b"NOT-AN-HTTP-STATUS-LINE\r\n\r\n")
                except OSError:
                    return
                return
            if self.mode == "stall_body":
                try:
                    conn.sendall(b"HTTP/1.1 200 OK\r\n"
                                 b"Content-Type: application/json\r\n"
                                 b"Content-Length: 4096\r\n\r\n")
                except OSError:
                    return
            # stall_header sends nothing; both stalls then wait to be torn down.
            while not self._stop.wait(0.05):
                pass

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}/v0/city/test-city/events"

    def close(self) -> None:
        self._stop.set()
        try:
            self.sock.close()
        except OSError:
            pass
        self._thread.join(timeout=2)


@pytest.fixture
def listener(request: pytest.FixtureRequest):
    made: list[_Listener] = []

    def _make(mode: str) -> _Listener:
        lis = _Listener(mode)
        made.append(lis)
        return lis

    yield _make
    for lis in made:
        lis.close()


@pytest.mark.parametrize("mode", ["stall_body", "stall_header"])
def test_a_stalled_response_raises_gcapierror_not_a_bare_timeout(listener, mode) -> None:
    """The documented contract is "transport failure raises GCAPIError".

    A timeout during the response read arrives as TimeoutError, which is
    an OSError and NOT a urllib URLError, so it passes through handlers
    that name only HTTPError and URLError. Callers that catch GCAPIError
    to degrade a section then do not degrade: the exception leaves the
    process and takes the whole command with it (dr-3lhmr: gc slack
    status died here on the inbound events read, with the adapters
    result already in hand and the bindings read never reached).
    """
    common = _import_common()
    lis = listener(mode)
    started = time.monotonic()
    with pytest.raises(common.GCAPIError) as excinfo:
        common._request("GET", lis.url, csrf=False, timeout=0.5)
    elapsed = time.monotonic() - started
    assert elapsed < 10, f"the timeout did not bound the call ({elapsed:.1f}s)"
    assert lis.url in str(excinfo.value)


def test_a_connection_reset_mid_response_raises_gcapierror(listener) -> None:
    """Same contract, different transport failure, so the fix cannot be
    a special case for one exception type.

    A reset during the response read arrives as ConnectionResetError,
    another OSError that is not a URLError, and it reaches callers the
    same way a timeout does."""
    common = _import_common()
    lis = listener("reset")
    with pytest.raises(common.GCAPIError):
        common._request("GET", lis.url, csrf=False, timeout=5)


def test_a_refused_connection_still_raises_gcapierror() -> None:
    """The case that already worked, kept so a fix cannot regress it:
    connection refused arrives as URLError and must keep converting."""
    common = _import_common()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    with pytest.raises(common.GCAPIError):
        common._request("GET", f"http://127.0.0.1:{port}/v0/city/test-city/events",
                        csrf=False, timeout=5)


def test_a_body_shorter_than_its_content_length_raises_gcapierror(listener) -> None:
    """A peer that under-delivers its own Content-Length and then closes
    cleanly raises http.client.IncompleteRead.

    HTTPException descends from Exception, not OSError, so neither the
    URLError clause nor the catch-all OSError clause reaches it, and
    urllib converts only failures raised while SENDING the request. It
    escapes for the same structural reason the bare TimeoutError did.
    """
    common = _import_common()
    lis = listener("short_body")
    with pytest.raises(common.GCAPIError) as excinfo:
        common._request("GET", lis.url, csrf=False, timeout=5)
    assert "IncompleteRead" in str(excinfo.value)


def test_a_malformed_status_line_raises_gcapierror(listener) -> None:
    """The other HTTPException that reaches a caller of this function:
    a peer answering on the right port with something that is not HTTP
    raises BadStatusLine out of getresponse()."""
    common = _import_common()
    lis = listener("bad_status")
    with pytest.raises(common.GCAPIError) as excinfo:
        common._request("GET", lis.url, csrf=False, timeout=5)
    assert "BadStatusLine" in str(excinfo.value)


def test_an_unreadable_error_body_still_reports_the_status_code(listener) -> None:
    """The HTTPError branch reads the error body, and that read fails the
    same ways the main one does.

    An exception raised inside an except clause is not offered to the
    remaining clauses of the same try statement, so a failing error-body
    read escapes uncaught however many transport clauses follow it. The
    status code is already in hand when that happens and must survive.
    """
    common = _import_common()
    lis = listener("error_short_body")
    with pytest.raises(common.GCAPIError) as excinfo:
        common._request("GET", lis.url, csrf=False, timeout=5)
    message = str(excinfo.value)
    assert "-> 500" in message
    assert "error body unreadable" in message
