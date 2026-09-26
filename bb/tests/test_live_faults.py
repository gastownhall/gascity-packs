"""Real HTTP fixture checks of fault mechanics; these do not certify BB or GC."""

import copy
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from live_faults import FaultFailure, FaultProxy, verify_recovery


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.requests = []
        self.response_status = 202
        self.response_body = {"status": "accepted", "request_id": "real-fixture-request", "event_cursor": "9"}
        owner = self

        class Upstream(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_):
                pass

            def do_POST(self):
                raw = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                owner.requests.append((self.command, self.path, raw))
                payload = json.dumps(owner.response_body).encode()
                self.send_response(owner.response_status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def do_GET(self):
                owner.requests.append((self.command, self.path, b""))
                payload = b"event: frame\ndata: actual upstream bytes\n\n"
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
                self.wfile.flush()

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        self.server.daemon_threads = True
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.proxy = FaultProxy(f"http://127.0.0.1:{self.server.server_port}", artifacts=self.root / "private")
        self.addCleanup(self.proxy.close)

    def request(self, path, *, method="POST", body=b'{"message":"unique real request"}'):
        from urllib.parse import urlsplit
        endpoint = urlsplit(self.proxy.url)
        conn = http.client.HTTPConnection(endpoint.hostname, endpoint.port, timeout=3)
        self.addCleanup(conn.close)
        headers = {"Content-Type": "application/json"}
        if method == "GET":
            headers = {"Accept": "text/event-stream"}
            body = None
        conn.request(method, path, body=body, headers=headers)
        return conn.getresponse()

    def test_drops_accepted_create_only_after_upstream_and_never_retries(self):
        ticket = self.proxy.arm("create")
        with self.assertRaises(http.client.RemoteDisconnected):
            self.request("/v0/city/test/sessions")
        evidence = ticket.wait(2)
        self.assertEqual(evidence["fault"], "accepted-response-drop")
        self.assertEqual(evidence["accepted"], self.response_body)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(self.requests[0][2], b'{"message":"unique real request"}')
        self.assertEqual(json.loads((self.root / "private/request-0001.response").read_bytes()), self.response_body)
        self.assertEqual((self.root / "private/request-0001.response").stat().st_mode & 0o777, 0o600)
        # Disarmed after one fault: forwarding a later request is normal.
        response = self.request("/v0/city/test/sessions")
        self.assertEqual(response.status, 202)
        self.assertEqual(json.loads(response.read()), self.response_body)
        self.assertEqual(self.proxy.counts()["create"], 2)

    def test_rejected_or_malformed_acceptance_is_not_a_successful_fault(self):
        for status, body in ((400, {"error": "denied"}), (202, {"status": "accepted"})):
            with self.subTest(status=status, body=body):
                self.response_status, self.response_body = status, body
                if self.proxy._ticket is None:
                    ticket = self.proxy.arm("submit")
                response = self.request("/v0/city/test/session/s1/submit")
                self.assertEqual(response.status, status)
                self.assertEqual(json.loads(response.read()), body)
                with self.assertRaisesRegex(FaultFailure, "did not occur"):
                    ticket.wait(0.05)
        self.assertEqual(len(self.requests), 2)
        self.assertFalse(any(row.get("fault") for row in self.proxy.records()))

    def test_exact_session_path_does_not_drop_another_mutation(self):
        ticket = self.proxy.arm("submit", path="/v0/city/test/session/intended/submit")
        response = self.request("/v0/city/test/session/other/submit")
        self.assertEqual(json.loads(response.read()), self.response_body)
        with self.assertRaises(http.client.RemoteDisconnected):
            self.request("/v0/city/test/session/intended/submit")
        self.assertEqual(ticket.wait(2)["path"], "/v0/city/test/session/intended/submit")
        self.assertEqual(len(self.requests), 2)

    def test_stream_disconnect_forwards_only_real_prefix_and_records_it(self):
        ticket = self.proxy.arm("stream", after_bytes=17)
        response = self.request("/v0/city/test/session/s1/stream?format=structured", method="GET")
        self.assertEqual(response.status, 200)
        with self.assertRaises(http.client.IncompleteRead) as caught:
            response.read()
        self.assertEqual(caught.exception.partial, b"event: frame\ndata")
        evidence = ticket.wait(2)
        self.assertEqual(evidence["fault"], "stream-disconnect")
        self.assertEqual(evidence["response_bytes"], 17)
        self.assertEqual((self.root / "private/request-0001.response").read_bytes(), caught.exception.partial)
        self.assertEqual(len(self.requests), 1)

    def test_session_stream_prefix_ignores_startup_and_other_session_streams(self):
        prefix = "/v0/city/test/session/intended/stream?"
        ticket = self.proxy.arm("stream", path_prefix=prefix, after_bytes=1)
        for path in ("/v0/city/test/events/stream?after_seq=1", "/v0/city/test/session/other/stream?after_cursor=before"):
            response = self.request(path, method="GET")
            self.assertEqual(response.read(), b"event: frame\ndata: actual upstream bytes\n\n")
        response = self.request(prefix + "format=structured&after_cursor=changing-cursor", method="GET")
        with self.assertRaises(http.client.IncompleteRead) as caught:
            response.read()
        self.assertEqual(caught.exception.partial, b"e")
        self.assertTrue(ticket.wait(2)["path"].startswith(prefix))
        self.assertEqual(len(self.requests), 3)

    def test_stream_prefix_cannot_target_arbitrary_routes(self):
        for prefix in ("/stream?", "/v0/city/test/events/stream?", "http://127.0.0.1/session/s1/stream?"):
            with self.subTest(prefix=prefix), self.assertRaisesRegex(FaultFailure, "one exact session"):
                self.proxy.arm("stream", path_prefix=prefix)

    def test_armed_fault_cannot_be_silently_replaced(self):
        self.proxy.arm("create")
        with self.assertRaisesRegex(FaultFailure, "already armed"):
            self.proxy.arm("submit")

    def test_hold_proves_acceptance_before_parent_releases_uncertain_reply(self):
        ticket = self.proxy.arm("submit", hold=True)
        outcomes = []
        def request():
            try:
                self.request("/v0/city/test/session/s1/submit")
            except http.client.RemoteDisconnected:
                outcomes.append("disconnected")
        thread = threading.Thread(target=request)
        thread.start()
        accepted = ticket.wait_accepted(2)
        self.assertEqual(accepted["accepted"], self.response_body)
        self.assertEqual(outcomes, [])
        self.assertTrue(thread.is_alive())
        self.assertEqual(json.loads((self.root / "private/request-0001.response").read_bytes()), self.response_body)
        ticket.release()
        self.assertTrue(ticket.wait(2)["hold_released"])
        thread.join(2)
        self.assertEqual(outcomes, ["disconnected"])
        self.assertEqual(len(self.requests), 1)

    def test_external_endpoint_and_existing_evidence_are_rejected(self):
        for url in ("http://example.com:80", "http://127.0.0.1", "https://127.0.0.1:443",
                    "http://user:secret@127.0.0.1:80", "http://127.0.0.1:80/path"):
            with self.subTest(url=url), self.assertRaises(FaultFailure):
                FaultProxy(url, artifacts=self.root / "unused")
        with self.assertRaises(FileExistsError):
            FaultProxy(f"http://127.0.0.1:{self.server.server_port}", artifacts=self.root / "private")


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.prompt = "first line\nunique full second line"
        self.forwarded = "BB context\nUser request:\n" + self.prompt
        self.before = {"threadId": "thread-1", "alias": "bb-alias", "sessionId": "gc-1",
                       "target": {"v": 1, "city": "test", "connection": "local", "agent": "mayor"}}
        self.after = {**self.before, "turn": {"state": "completed", "request_id": "submit-1", "event_cursor": "2",
                                             "messageDigest": hashlib.sha256(self.forwarded.encode()).hexdigest(),
                                             "digest": hashlib.sha256(self.prompt.encode()).hexdigest()}}
        self.frame = {"id": "gc-1", "schema_version": "session.structured.v1", "history": {
            "gc_session_id": "native-conversation-uuid", "logical_conversation_id": "native-conversation-uuid",
            "provider_session_id": "native-conversation-uuid", "transcript_stream_id": "native-stream-id",
            "tail_state": {"activity": "idle"}},
                      "structured_messages": [{"id": "gc-message-1", "role": "user",
                                               "user_prompt": {"text": self.forwarded}}]}
        self.records = [{"method": "POST", "path": path, "upstream_status": 202, "finished_at": 1,
                         "accepted": {"status": "accepted", "request_id": "submit-1", "event_cursor": "2"}}
                        for path in ("/v0/city/test/sessions", "/v0/city/test/session/gc-1/submit")]

    def verify(self, **changes):
        args = {"before": self.before, "after": self.after, "transcript": self.frame,
                "request_records": self.records, "expected_prompt": self.prompt}
        args.update(changes)
        return verify_recovery(**args)

    def test_one_independent_prompt_and_unchanged_identity_pass(self):
        self.assertEqual(self.verify()["submit_requests"], 1)

    def test_api_session_identity_cannot_be_replaced_by_native_history_identity(self):
        for session_id in (None, "different"):
            frame = copy.deepcopy(self.frame)
            frame["id"] = session_id
            frame["history"]["gc_session_id"] = "gc-1"
            with self.subTest(id=session_id), self.assertRaisesRegex(FaultFailure, "different GC session"):
                self.verify(transcript=frame)

    def test_complete_native_history_identity_is_required(self):
        for field in ("gc_session_id", "logical_conversation_id", "provider_session_id", "transcript_stream_id"):
            for invalid in (None, "", " ", 1):
                frame = copy.deepcopy(self.frame)
                frame["history"][field] = invalid
                with self.subTest(field=field, invalid=invalid), self.assertRaisesRegex(FaultFailure, "history identit"):
                    self.verify(transcript=frame)
        frame = {**self.frame, "history": None}
        with self.assertRaisesRegex(FaultFailure, "history identit"):
            self.verify(transcript=frame)

    def test_duplicate_or_truncated_prompt_fails(self):
        frame = copy.deepcopy(self.frame)
        frame["structured_messages"].append(copy.deepcopy(frame["structured_messages"][0]))
        with self.assertRaisesRegex(FaultFailure, "exactly one"):
            self.verify(transcript=frame)
        frame["structured_messages"] = frame["structured_messages"][:1]
        frame["structured_messages"][0]["user_prompt"]["text"] = "first line"
        with self.assertRaisesRegex(FaultFailure, "exactly one"):
            self.verify(transcript=frame)

    def test_resent_mutation_changed_session_and_incomplete_capture_fail(self):
        with self.assertRaisesRegex(FaultFailure, "resent"):
            self.verify(request_records=self.records + [self.records[1]])
        with self.assertRaisesRegex(FaultFailure, "exact GC session"):
            self.verify(after={**self.after, "sessionId": "different"})
        records = copy.deepcopy(self.records)
        records[1].pop("finished_at")
        with self.assertRaisesRegex(FaultFailure, "unfinished"):
            self.verify(request_records=records)

    def test_unknown_create_can_be_verified_against_independent_session_identity(self):
        before = {key: value for key, value in self.before.items() if key != "sessionId"}
        with self.assertRaisesRegex(FaultFailure, "exact GC session"):
            self.verify(before=before)
        self.assertEqual(self.verify(before=before, expected_session_id="gc-1")["session_id"], "gc-1")

    def test_unsettled_turn_or_changed_acceptance_cannot_pass(self):
        after = copy.deepcopy(self.after)
        after["turn"]["state"] = "uncertain"
        with self.assertRaisesRegex(FaultFailure, "not completed"):
            self.verify(after=after)
        after["turn"]["state"] = "completed"
        after["turn"]["request_id"] = "different"
        with self.assertRaisesRegex(FaultFailure, "independently captured"):
            self.verify(after=after)


if __name__ == "__main__":
    unittest.main()
