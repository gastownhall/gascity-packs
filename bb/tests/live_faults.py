"""One-shot transport faults in front of a real loopback GC service.

This proxy never retries a request or creates a provider reply. It records real
upstream bytes privately before dropping an accepted response, or forwards a
prefix of a real event stream before disconnecting. Fixture tests certify only
the proxy mechanics; callers must verify the actual GC and BB evidence.
"""

import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import socket
import threading
import time
from urllib.parse import urlsplit


class FaultFailure(RuntimeError):
    pass


def _write_new(path, data):
    with path.open("xb") as stream:
        import os
        os.fchmod(stream.fileno(), 0o600)
        stream.write(data)


class FaultTicket:
    """A fault is observed only when its real upstream response was intercepted."""

    def __init__(self, kind, path, after_bytes, hold, path_prefix=None):
        self.kind, self.path, self.after_bytes = kind, path, after_bytes
        self.path_prefix = path_prefix
        self.hold = hold
        self.evidence = None
        self._done = threading.Event()
        self._accepted = threading.Event()
        self._release = threading.Event()

    def wait(self, timeout=30):
        if not self._done.wait(timeout):
            raise FaultFailure("The armed transport fault did not occur before its deadline")
        return dict(self.evidence)

    def wait_accepted(self, timeout=30):
        """Inspect accepted bytes while a held response cannot reach BB yet."""
        if not self.hold or not self._accepted.wait(timeout):
            raise FaultFailure("No held, accepted upstream response was observed")
        return dict(self.evidence)

    def release(self):
        """Let a held response be dropped after an explicit lifecycle action."""
        self._release.set()


class FaultProxy:
    """Threaded HTTP/1.1 proxy, bound only to 127.0.0.1 and forwarding once.

    ``artifacts`` must be a new, private path inside the caller's scratch root.
    Arm one fault at a time. An optional exact path (including query) prevents a
    startup stream or another session from consuming a turn-specific fault.
    """

    _hop_headers = {"connection", "proxy-connection", "keep-alive", "te",
                    "trailer", "transfer-encoding", "upgrade", "proxy-authenticate",
                    "proxy-authorization"}
    _mutation_paths = {
        "create": re.compile(r"^/v0/city/[^/]+/sessions$"),
        "submit": re.compile(r"^/v0/city/[^/]+/session/[^/]+/submit$"),
    }

    def __init__(self, upstream_url, *, artifacts, timeout=30):
        upstream = urlsplit(upstream_url)
        if (upstream.scheme != "http" or upstream.hostname not in {"127.0.0.1", "::1"}
                or upstream.username or upstream.password or upstream.path not in {"", "/"}
                or upstream.query or upstream.fragment or not upstream.port):
            raise FaultFailure("Fault proxy requires an explicit loopback HTTP host and port")
        if timeout <= 0:
            raise FaultFailure("Fault proxy timeout must be positive")
        self.upstream, self.timeout = upstream, timeout
        self.artifacts = Path(artifacts)
        self.artifacts.mkdir(mode=0o700, parents=True, exist_ok=False)
        self._lock, self._records = threading.Lock(), []
        self._ticket = None
        self._connections = set()
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), self._handler())
        self._server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self._server.server_port}"
        self._thread = threading.Thread(target=self._server.serve_forever,
                                        name="gc-fault-proxy", daemon=True)
        self._thread.start()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        self._server.shutdown()
        self._server.server_close()
        with self._lock:
            connections = list(self._connections)
        for connection in connections:
            connection.close()
        self._thread.join(timeout=2)

    def arm(self, kind, *, path=None, path_prefix=None, after_bytes=1, hold=False):
        if kind not in {"create", "submit", "stream"}:
            raise FaultFailure("Unknown transport fault")
        if path is not None and (not path.startswith("/") or path.startswith("//")):
            raise FaultFailure("Fault path must be an exact local request path")
        if path_prefix is not None and (kind != "stream" or path is not None
                or re.fullmatch(r"/v0/city/[^/]+/session/[^/]+/stream\?", path_prefix) is None):
            raise FaultFailure("A stream prefix must identify one exact session stream route")
        if type(after_bytes) is not int or after_bytes < 1:
            raise FaultFailure("Stream faults require at least one real forwarded byte")
        if hold and kind == "stream":
            raise FaultFailure("Only accepted mutation responses can be held")
        with self._lock:
            if self._ticket is not None:
                raise FaultFailure("A transport fault is already armed or in flight")
            self._ticket = FaultTicket(kind, path, after_bytes, hold, path_prefix)
            return self._ticket

    def records(self):
        with self._lock:
            return [dict(record) for record in self._records]

    def counts(self):
        records = self.records()
        return {kind: sum(row.get("operation") == kind for row in records)
                for kind in ("create", "submit", "stream")}

    def _operation(self, method, path, headers):
        route = urlsplit(path).path
        if method == "POST":
            for kind, pattern in self._mutation_paths.items():
                if pattern.fullmatch(route):
                    return kind
        if method == "GET" and "text/event-stream" in headers.get("Accept", ""):
            return "stream"
        return "read" if method == "GET" else "other"

    def _select(self, operation, path):
        with self._lock:
            ticket = self._ticket
            if (ticket and ticket.kind == operation and not hasattr(ticket, "_claimed")
                    and (ticket.path is None or ticket.path == path)
                    and (ticket.path_prefix is None or path.startswith(ticket.path_prefix))):
                ticket._claimed = True
                return ticket
        return None

    def _finish_ticket(self, ticket, record):
        with self._lock:
            if ticket and record.get("fault"):
                ticket.evidence = dict(record)
                self._ticket = None
                ticket._done.set()
            elif ticket:
                # An error/non-accepted response is not the requested fault.
                # Keep it armed, but never retry that upstream operation.
                del ticket._claimed

    def _handler(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_):
                pass  # Provider bodies, paths and tokens remain private.

            def do_GET(self):
                self.forward()

            def do_POST(self):
                self.forward()

            def do_DELETE(self):
                self.forward()

            def do_PATCH(self):
                self.forward()

            def do_PUT(self):
                self.forward()

            def disconnect(self):
                self.close_connection = True
                try:
                    self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

            def forward(self):
                target = urlsplit(self.path)
                if target.scheme or target.netloc or not self.path.startswith("/"):
                    self.send_error(400, "Only local request paths are supported")
                    return
                if self.headers.get("Transfer-Encoding"):
                    self.send_error(400, "Chunked request bodies are not supported")
                    return
                try:
                    length = int(self.headers.get("Content-Length", "0"))
                except ValueError:
                    length = -1
                if not 0 <= length <= 8 * 1024 * 1024:
                    self.send_error(413, "Request body is outside the capture limit")
                    return
                body = self.rfile.read(length)
                if len(body) != length:
                    self.disconnect()
                    return
                operation = owner._operation(self.command, self.path, self.headers)
                with owner._lock:
                    record = {"index": len(owner._records) + 1, "method": self.command,
                              "path": self.path, "operation": operation,
                              "request_bytes": len(body),
                              "request_sha256": hashlib.sha256(body).hexdigest(),
                              "started_at": time.time()}
                    owner._records.append(record)
                prefix = owner.artifacts / f"request-{record['index']:04d}"
                _write_new(prefix.with_suffix(".body"), body)
                ticket = owner._select(operation, self.path)
                connection = http.client.HTTPConnection(owner.upstream.hostname,
                                                        owner.upstream.port, timeout=owner.timeout)
                with owner._lock:
                    owner._connections.add(connection)
                response_started = False
                try:
                    connection_tokens = {token.strip().lower() for token in
                                         self.headers.get("Connection", "").split(",")}
                    headers = {key: value for key, value in self.headers.items()
                               if key.lower() not in owner._hop_headers | connection_tokens | {"host"}}
                    headers["Connection"] = "close"
                    # Keep captured accepted JSON and streamed bytes directly
                    # inspectable; neither side receives fabricated content.
                    headers["Accept-Encoding"] = "identity"
                    connection.request(self.command, self.path, body=body, headers=headers)
                    response = connection.getresponse()
                    record["upstream_status"] = response.status
                    is_stream = "text/event-stream" in response.getheader("Content-Type", "")
                    if is_stream:
                        stream_ticket = ticket if 200 <= response.status < 300 else None
                        self.send_response_only(response.status, response.reason)
                        self.forward_headers(response)
                        self.end_headers()
                        response_started = True
                        digest, total = hashlib.sha256(), 0
                        with prefix.with_suffix(".response").open("xb") as evidence:
                            import os
                            os.fchmod(evidence.fileno(), 0o600)
                            while True:
                                size = min(4096, stream_ticket.after_bytes - total) if stream_ticket else 4096
                                chunk = response.read1(size)
                                if not chunk:
                                    break
                                evidence.write(chunk)
                                evidence.flush()
                                digest.update(chunk)
                                total += len(chunk)
                                self.wfile.write(chunk)
                                self.wfile.flush()
                                if stream_ticket and total >= stream_ticket.after_bytes:
                                    record["fault"] = "stream-disconnect"
                                    break
                        record.update(response_bytes=total, response_sha256=digest.hexdigest())
                    else:
                        raw = response.read(8 * 1024 * 1024 + 1)
                        _write_new(prefix.with_suffix(".response"), raw)
                        record.update(response_bytes=len(raw), response_sha256=hashlib.sha256(raw).hexdigest())
                        if len(raw) > 8 * 1024 * 1024:
                            raise FaultFailure("GC response exceeded the private capture limit")
                        accepted = None
                        if operation in {"create", "submit"} and 200 <= response.status < 300:
                            try:
                                accepted = json.loads(raw)
                            except (ValueError, UnicodeError):
                                pass
                            if (isinstance(accepted, dict) and accepted.get("status") == "accepted"
                                    and isinstance(accepted.get("request_id"), str) and accepted["request_id"]
                                    and accepted.get("event_cursor") is not None):
                                record["accepted"] = accepted
                                if ticket:
                                    record["fault"] = "accepted-response-drop"
                                if ticket and ticket.hold:
                                    # Save evidence before announcing the hold:
                                    # callers may now interrupt only their own
                                    # bridge while BB lacks the accepted reply.
                                    ticket.evidence = dict(record)
                                    ticket._accepted.set()
                                    record["hold_released"] = ticket._release.wait(owner.timeout)
                        if not record.get("fault"):
                            self.send_response_only(response.status, response.reason)
                            self.forward_headers(response)
                            self.end_headers()
                            response_started = True
                            self.wfile.write(raw)
                            self.wfile.flush()
                except Exception as error:
                    record["transport_error"] = type(error).__name__
                    if not response_started and not record.get("fault"):
                        # A real transport failure remains an HTTP failure.
                        try:
                            self.send_error(502, "Upstream transport failed; inspect private evidence")
                        except OSError:
                            pass
                finally:
                    self.disconnect()
                    connection.close()
                    with owner._lock:
                        owner._connections.discard(connection)
                    record["finished_at"] = time.time()
                    _write_new(prefix.with_suffix(".json"), json.dumps(record, indent=2).encode())
                    owner._finish_ticket(ticket, record)

            def forward_headers(self, response):
                connection_tokens = {token.strip().lower() for token in
                                     response.getheader("Connection", "").split(",")}
                for key, value in response.getheaders():
                    if key.lower() not in owner._hop_headers | connection_tokens:
                        self.send_header(key, value)
                self.send_header("Connection", "close")

        return Handler


def verify_recovery(*, before, after, transcript, request_records, expected_prompt,
                    expected_session_id=None):
    """Require retained ownership plus one real prompt and no resent mutation.

    Supply the exact thread's durable receipts, the complete independent GC
    structured transcript, and proxy records since before its creation. This
    only validates evidence; it never performs or approves recovery itself.
    """
    for field in ("threadId", "target", "alias"):
        if not before.get(field) or before[field] != after.get(field):
            raise FaultFailure("Recovery changed the thread's durable ownership")
    session_id = expected_session_id or before.get("sessionId")
    if not session_id or after.get("sessionId") != session_id:
        raise FaultFailure("Recovery did not preserve the exact GC session")
    if before.get("sessionId") and before["sessionId"] != session_id:
        raise FaultFailure("Expected GC session disagrees with original receipt")
    if transcript.get("schema_version") != "session.structured.v1":
        raise FaultFailure("Recovery evidence lacks a structured GC transcript")
    # The API resource ID identifies the session bead. Native history IDs are
    # opaque conversation/stream identities and need not equal that resource ID.
    if transcript.get("id") != session_id:
        raise FaultFailure("Recovery transcript belongs to a different GC session")
    history = transcript.get("history")
    if not isinstance(history, dict) or any(
            not isinstance(history.get(field), str) or not history[field].strip()
            for field in ("gc_session_id", "logical_conversation_id", "provider_session_id", "transcript_stream_id")):
        raise FaultFailure("Recovery transcript lacks complete native history identities")
    tail = history.get("tail_state") or {}
    if (tail.get("activity") != "idle" or tail.get("degraded", False) is not False
            or tail.get("pending_interaction_ids") or tail.get("open_tool_call_ids")):
        raise FaultFailure("Recovery transcript is not reliably settled")
    messages = transcript.get("structured_messages")
    if not isinstance(messages, list) or not expected_prompt:
        raise FaultFailure("Recovery evidence lacks the complete expected prompt")
    matching = []
    for message in messages:
        if message.get("role") != "user" or message.get("status") == "superseded":
            continue
        text = (message.get("user_prompt") or {}).get("text")
        if text is None:
            text = "\n".join(block.get("text", "") for block in message.get("blocks", [])
                             if block.get("type") == "text")
        if isinstance(text, str) and expected_prompt in text:
            matching.append((message, text))
    if len(matching) != 1 or matching[0][1].count(expected_prompt) != 1:
        raise FaultFailure("Recovery transcript does not contain exactly one complete user prompt")
    message, text = matching[0]
    if not message.get("id"):
        raise FaultFailure("Recovered prompt has no independent GC message identity")
    turn = after.get("turn") or {}
    if (turn.get("state") != "completed" or not turn.get("request_id")
            or turn.get("messageDigest") != hashlib.sha256(text.encode()).hexdigest()
            or turn.get("digest") != hashlib.sha256(expected_prompt.encode()).hexdigest()):
        raise FaultFailure("Recovery receipt is not completed for the exact delivered prompt")
    target = after["target"]
    from urllib.parse import quote
    city_path = "/v0/city/" + quote(target["city"], safe="")
    create_path, submit_path = city_path + "/sessions", city_path + "/session/" + quote(session_id, safe="") + "/submit"
    creates = [record for record in request_records
               if record.get("method") == "POST" and record.get("path") == create_path]
    submits = [record for record in request_records
               if record.get("method") == "POST" and record.get("path") == submit_path]
    if len(creates) != 1 or len(submits) != 1:
        raise FaultFailure("Recovery resent creation or submission, or lacks complete request evidence")
    if any(not record.get("finished_at") or not 200 <= record.get("upstream_status", 0) < 300
           or (record.get("accepted") or {}).get("status") != "accepted"
           for record in creates + submits):
        raise FaultFailure("Recovery mutation evidence is unfinished or not accepted upstream")
    if (submits[0]["accepted"].get("request_id") != turn["request_id"]
            or submits[0]["accepted"].get("event_cursor") != turn.get("event_cursor")):
        raise FaultFailure("Recovery did not retain the independently captured submit acceptance")
    return {"session_id": session_id, "gc_user_message_id": message["id"],
            "create_requests": 1, "submit_requests": 1,
            "forwarded_prompt_sha256": turn["messageDigest"]}
