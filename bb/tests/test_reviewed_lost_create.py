"""Guard-only tests: explicit captured lost-create evidence is never a generic bypass."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from live_assertions import AcceptanceFailure
from full_e2e import Runner
import test_live_assertions


class ReviewedLostCreateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.harness, self.prompt, self.provider = test_live_assertions.PersonalTargetConfigTests().harness(Path(temp.name).resolve())
        self.path = (Path(self.harness.env["XDG_STATE_HOME"]) / "gascity/bb/sessions" /
                     (hashlib.sha256(self.harness.thread_id.encode()).hexdigest() + ".json"))
        self.receipt = json.loads(self.path.read_text())
        self.receipt.pop("create")
        self.receipt["alias"] = "bb-" + hashlib.sha256(self.harness.thread_id.encode()).hexdigest()[:24]
        self.save()
        self.session = {"id": "gc-session", "template": "global", "alias": self.receipt["alias"],
                        "work_dir": str(self.harness.workspace)}
        request = json.dumps({"kind": "agent", "name": "global", "alias": self.receipt["alias"],
                              "project_id": "proj_personal"})
        accepted = {"status": "accepted", "request_id": "gc-create", "event_cursor": "1"}
        response = json.dumps(accepted)
        self.evidence = {
            "kind": "reviewed-lost-create",
            "before_receipt": {key: self.receipt[key] for key in ("threadId", "target", "alias")},
            "session": copy.deepcopy(self.session), "request_body": request, "response_body": response,
            "intercepted": {"index": 1, "method": "POST", "operation": "create",
                "path": "/v0/city/test-city/sessions", "fault": "accepted-response-drop",
                "upstream_status": 202, "finished_at": 123, "accepted": accepted,
                "request_bytes": len(request.encode()), "request_sha256": hashlib.sha256(request.encode()).hexdigest(),
                "response_bytes": len(response.encode()), "response_sha256": hashlib.sha256(response.encode()).hexdigest()}}

    def save(self):
        self.path.write_text(json.dumps(self.receipt))

    def response(self, request, timeout):
        if request.full_url.endswith("/config"):
            data = {"agents": [{"name": "global"}]}
        elif "/transcript?" in request.full_url:
            data = {"schema_version": "session.structured.v1", "history": {"tail_state": {"activity": "idle"}},
                    "structured_messages": [{"id": "new-user", "role": "user", "user_prompt": {"text": self.prompt}}]}
        else:
            data = self.session
        return io.BytesIO(json.dumps(data).encode())

    def verify(self, evidence):
        with patch("live_assertions.urllib.request.build_opener") as opener:
            opener.return_value.open.side_effect = self.response
            self.harness.verify_gc_prompt(self.prompt, self.provider, reviewed_creation=evidence)

    def test_missing_create_remains_failure_without_explicit_evidence(self):
        with self.assertRaisesRegex(AcceptanceFailure, "acceptance identities"):
            self.harness.verify_gc_prompt(self.prompt, self.provider)

    def test_explicit_reviewed_lost_create_preserves_full_prompt_verification(self):
        self.verify(self.evidence)
        turn = self.harness.report["turns"][-1]
        self.assertEqual(turn["gc_create_request_id"], "gc-create")
        self.assertEqual(turn["gc_create_event_cursor"], "1")
        self.assertEqual(turn["gc_user_message_id"], "new-user")
        self.assertEqual(turn["gc_submit_request_id"], "gc-submit")

    def test_wrong_ownership_or_intercept_cannot_supply_create_evidence(self):
        changes = [
            lambda e: e.update(kind="generic-recovery"),
            lambda e: e["before_receipt"].update(threadId="another-thread"),
            lambda e: e["before_receipt"]["target"].update(connection="another-target"),
            lambda e: e["before_receipt"].update(alias="wrong-alias"),
            lambda e: e["before_receipt"].update(create={"request_id": "unexpected"}),
            lambda e: e["session"].update(id="replacement-session"),
            lambda e: e["session"].update(alias="wrong-alias"),
            lambda e: e["session"].update(template="another-agent"),
            lambda e: e["session"].update(work_dir="/different-workspace"),
            lambda e: e["intercepted"].update(path="/v0/city/other/sessions"),
            lambda e: e["intercepted"].update(fault="not-dropped"),
            lambda e: e["intercepted"].update(upstream_status=500),
            lambda e: e["intercepted"]["accepted"].update(event_cursor="different-cursor"),
            lambda e: e["intercepted"]["accepted"].update(request_id="different-request"),
            lambda e: e.update(request_body=e["request_body"] + " "),
        ]
        for change in changes:
            evidence = copy.deepcopy(self.evidence)
            change(evidence)
            with self.subTest(change=changes.index(change)), self.assertRaises(AcceptanceFailure):
                self.verify(evidence)

    def test_lost_create_evidence_cannot_replace_submit_acceptance(self):
        self.receipt["turn"].pop("request_id")
        self.save()
        with self.assertRaisesRegex(AcceptanceFailure, "acceptance identities"):
            self.verify(self.evidence)

    def test_live_alias_must_still_match_reviewed_session(self):
        self.session["alias"] = "different-live-alias"
        with self.assertRaisesRegex(AcceptanceFailure, "alias"):
            self.verify(self.evidence)

    def test_both_receipts_cannot_agree_on_non_deterministic_alias(self):
        self.receipt["alias"] = "not-the-thread-alias"
        self.save()
        self.evidence["before_receipt"]["alias"] = self.receipt["alias"]
        with self.assertRaises(AcceptanceFailure):
            self.verify(self.evidence)

    def test_prompt_digest_guard_is_not_weakened(self):
        self.receipt["turn"]["digest"] = "wrong"
        self.save()
        with self.assertRaisesRegex(AcceptanceFailure, "original user prompt"):
            self.verify(self.evidence)

    def test_hashed_create_body_must_identify_original_alias_target_and_project(self):
        for key, wrong in [("alias", "other-alias"), ("name", "other-agent"),
                           ("project_id", "other-project"), ("kind", "shell")]:
            evidence = copy.deepcopy(self.evidence)
            body = json.loads(evidence["request_body"])
            body[key] = wrong
            text = json.dumps(body)
            evidence["request_body"] = text
            evidence["intercepted"].update(request_bytes=len(text.encode()),
                                         request_sha256=hashlib.sha256(text.encode()).hexdigest())
            with self.subTest(key=key), self.assertRaises(AcceptanceFailure):
                self.verify(evidence)

    def test_evidence_cannot_override_an_observed_create_ack_or_later_turn(self):
        self.receipt["create"] = {"request_id": "other-create", "event_cursor": "10"}
        self.save()
        with self.assertRaises(AcceptanceFailure):
            self.verify(self.evidence)
        self.receipt.pop("create")
        self.save()
        self.harness.report["turns"].append({"client_request_id": "test-request"})
        with self.assertRaisesRegex(AcceptanceFailure, "first recovered turn"):
            self.verify(self.evidence)

    def test_runner_only_forwards_creation_evidence_when_explicitly_supplied(self):
        runner = object.__new__(Runner)
        for evidence in (None, self.evidence):
            harness = Mock()
            harness.await_turn.return_value = (10, self.provider)
            harness.verify_gc_prompt.side_effect = AcceptanceFailure("stop after forwarding")
            kwargs = {} if evidence is None else {"reviewed_creation": evidence}
            with self.subTest(explicit=evidence is not None), self.assertRaisesRegex(AcceptanceFailure, "stop after forwarding"):
                runner.verify_turn(harness, {"afterSeq": 1}, self.prompt, "MARKER", **kwargs)
            harness.verify_gc_prompt.assert_called_once_with(self.prompt, self.provider, **kwargs)
