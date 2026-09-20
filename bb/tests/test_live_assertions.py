"""Unit checks for acceptance guards; these do not run or certify a model."""

import base64
import copy
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from live_assertions import AcceptanceFailure, LiveAssertions, safe_provider_failure, verify_prompt_frame, verify_resume_identity, verify_global_agent_config


def completed_events():
    scope = {"kind": "turn", "turnId": "test-turn-1"}
    return [
        {"seq": 1, "type": "client/turn/requested", "scope": {"kind": "thread"},
         "data": {"requestId": "test-request", "execution": {"model": "exact-agent"}}},
        {"seq": 2, "type": "turn/started", "scope": scope,
         "data": {"providerThreadId": "test-gc-session"}},
        {"seq": 3, "type": "turn/input/accepted", "scope": scope,
         "data": {"clientRequestId": "test-request"}},
        {"seq": 4, "type": "item/completed", "scope": scope,
         "data": {"item": {"type": "agentMessage", "text": "TEST_MARKER"}}},
        {"seq": 5, "type": "turn/completed", "scope": scope,
         "data": {"status": "completed", "providerThreadId": "test-gc-session"}},
    ]



def agent_model(agent="global", city="test-city"):
    target = {"v": 1, "connection": "local", "city": city, "agent": agent}
    return "gc1_" + base64.urlsafe_b64encode(json.dumps(target).encode()).decode().rstrip("=")


class PersonalWorkspaceGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "gc-workspace"
        self.workspace.mkdir()
        self.data = self.root / "bb-data"
        self.personal = self.data / "personal-workspaces" / "env_test"
        self.personal.mkdir(parents=True)

    def harness(self, project="proj_personal", agent="global"):
        return LiveAssertions(bb_bin="unused", host="test-host", project=project,
                              model=agent_model(agent), workspace=self.workspace,
                              artifacts=self.root / "evidence", env={"BB_DATA_DIR": str(self.data)})

    def destination(self, harness, path=None):
        return {"thread": {"providerId": "gas-city", "projectId": harness.project},
                "environment": {"id": "env_test", "hostId": "test-host", "managed": False,
                                "path": str(path or self.personal)}}

    def test_personal_global_requires_separate_bb_owned_directory(self):
        harness = self.harness()
        with patch.object(harness, "command", return_value=self.destination(harness)):
            harness.verify_destination()
        self.assertIn("personal-global-separate-bb-workspace", harness.report["assertions"])
        for bad in (self.workspace, self.root, self.data / "other"):
            with self.subTest(path=bad), patch.object(harness, "command", return_value=self.destination(harness, bad)):
                with self.assertRaisesRegex(AcceptanceFailure, "personal workspace"):
                    harness.verify_destination()

    def test_personal_rig_cannot_bypass_project_binding(self):
        with self.assertRaisesRegex(AcceptanceFailure, "global agent"):
            self.harness(agent="sample/rig")

    def test_native_personal_workspace_is_managed_by_bb(self):
        harness = self.harness()
        destination = self.destination(harness)
        destination["environment"].update(managed=True, workspaceProvisionType="personal")
        with patch.object(harness, "command", return_value=destination):
            harness.verify_destination()
        destination["environment"]["workspaceProvisionType"] = "worktree"
        with patch.object(harness, "command", return_value=destination):
            with self.assertRaisesRegex(AcceptanceFailure, "personal workspace"):
                harness.verify_destination()

    def test_plugin_personal_workspace_requires_exact_thread_instance_and_owned_path(self):
        harness = self.harness()
        harness.thread_id = "thread_test"
        path = self.data / "plugins/environment-personal-workspace/host-data/workspaces/thread_test"
        path.mkdir(parents=True)
        destination = self.destination(harness, path)
        destination["environment"].update(managed=True, workspaceProvisionType="personal",
            environmentProviderId="personal-workspace", environmentProviderInstanceKey=harness.thread_id)
        with patch.object(harness, "command", return_value=destination):
            harness.verify_destination()
        for changed in ({"environmentProviderInstanceKey": "another_thread"},
                        {"environmentProviderId": "different-provider"}, {"managed": False},
                        {"workspaceProvisionType": "worktree"}, {"path": str(self.personal)},
                        {"path": "relative/personal-workspace"}):
            invalid = {**destination, "environment": {**destination["environment"], **changed}}
            with self.subTest(changed=changed), patch.object(harness, "command", return_value=invalid):
                with self.assertRaises(AcceptanceFailure): harness.verify_destination()

    def test_personal_workspace_cannot_escape_through_symlinks_or_thread_identity(self):
        harness = self.harness()
        harness.thread_id = "thread_test"
        path = self.data / "plugins/environment-personal-workspace/host-data/workspaces/thread_test"
        path.parent.mkdir(parents=True)
        outside = self.root / "outside"
        outside.mkdir()
        path.symlink_to(outside, target_is_directory=True)
        destination = self.destination(harness, path)
        destination["environment"].update(managed=True, workspaceProvisionType="personal",
            environmentProviderId="personal-workspace", environmentProviderInstanceKey=harness.thread_id)
        with patch.object(harness, "command", return_value=destination):
            with self.assertRaises(AcceptanceFailure): harness.verify_destination()
        for thread in ("..", ".", "../outside", "/absolute"):
            harness.thread_id = thread
            destination["environment"]["environmentProviderInstanceKey"] = thread
            with self.subTest(thread=thread), patch.object(harness, "command", return_value=destination):
                with self.assertRaises(AcceptanceFailure): harness.verify_destination()

    def test_legacy_layout_cannot_hide_plugin_identity_or_escape_its_data_directory(self):
        harness = self.harness()
        destination = self.destination(harness)
        destination["environment"]["environmentProviderInstanceKey"] = "thread_test"
        with patch.object(harness, "command", return_value=destination):
            with self.assertRaises(AcceptanceFailure): harness.verify_destination()
        destination["environment"].pop("environmentProviderInstanceKey")
        outside = self.root / "outside"
        outside.mkdir()
        self.personal.rename(self.personal.with_name("saved-personal"))
        self.personal.symlink_to(outside, target_is_directory=True)
        with patch.object(harness, "command", return_value=destination):
            with self.assertRaises(AcceptanceFailure): harness.verify_destination()

    def test_project_workspace_still_must_match_gc(self):
        harness = self.harness(project="project-sample", agent="sample/rig")
        with patch.object(harness, "command", return_value=self.destination(harness)):
            with self.assertRaisesRegex(AcceptanceFailure, "different workspace"):
                harness.verify_destination()
        with patch.object(harness, "command", return_value=self.destination(harness, self.workspace)):
            harness.verify_destination()

    def test_personal_spawn_lets_bb_choose_its_workspace(self):
        harness = self.harness()
        calls = []
        def command(*args):
            calls.append(args)
            return {"id": "test-thread"} if args[1] == "spawn" else self.destination(harness)
        with patch.object(harness, "command", side_effect=command), \
                patch.object(harness, "await_turn", side_effect=AcceptanceFailure("stop before model work")), \
                patch.object(harness, "progress"):
            with self.assertRaisesRegex(AcceptanceFailure, "stop before model work"):
                harness.run()
        spawn = calls[0]
        self.assertEqual(spawn[spawn.index("--project") + 1], "proj_personal")
        self.assertNotIn("--environment", spawn)

    def test_project_spawn_keeps_explicit_workspace(self):
        harness = self.harness(project="project-sample", agent="sample/rig")
        calls = []
        def command(*args):
            calls.append(args)
            return {"id": "test-thread"} if args[1] == "spawn" else self.destination(harness, self.workspace)
        with patch.object(harness, "command", side_effect=command), \
                patch.object(harness, "await_turn", side_effect=AcceptanceFailure("stop before model work")), \
                patch.object(harness, "progress"):
            with self.assertRaisesRegex(AcceptanceFailure, "stop before model work"):
                harness.run()
        self.assertEqual(calls[0][calls[0].index("--environment") + 1], str(self.workspace))

class PersonalTargetConfigTests(unittest.TestCase):
    def test_personal_agent_must_exist_as_active_global_in_exact_city_config(self):
        target = {"v": 1, "connection": "local", "city": "test-city", "agent": "global"}
        valid = {"workspace": {}, "agents": [{"name": "global"}]}
        verify_global_agent_config(target, valid)
        for config in (
                {"agents": []},
                {"agents": [{"name": "different"}]},
                {"agents": [{"name": "global", "dir": "sample"}]},
                {"agents": [{"name": "global", "scope": "rig"}]},
                {"agents": [{"name": "global", "suspended": True}]},
                {"workspace": {"suspended": True}, "agents": [{"name": "global"}]},
                {"agents": [{"name": "global"}, {"name": "global"}]}):
            with self.subTest(config=config), self.assertRaisesRegex(AcceptanceFailure, "active global agent"):
                verify_global_agent_config(target, config)

    def harness(self, root, project="proj_personal", agent="global"):
        workspace = root / "gc-workspace"
        workspace.mkdir()
        state = root / "state"
        receipts = state / "gascity/bb/sessions"
        receipts.mkdir(parents=True)
        config = root / "bb.json"
        config.write_text(json.dumps({"connections": [{"id": "local", "url": "http://127.0.0.1:12345"}], "bindings": []}))
        harness = LiveAssertions(bb_bin="unused", host="test-host", project=project,
                                 model=agent_model(agent), workspace=workspace, artifacts=root / "evidence",
                                 env={"GC_BB_CONFIG": str(config), "XDG_STATE_HOME": str(state)})
        harness.thread_id = "test-thread"
        harness.report["turns"] = [{"client_request_id": "test-request"}]
        target = {"v": 1, "connection": "local", "city": "test-city", "agent": agent}
        prompt = "Reply TEST_MARKER"
        turn = {"state": "completed", "clientRequestId": "test-request", "request_id": "gc-submit",
                "event_cursor": "2", "digest": hashlib.sha256(prompt.encode()).hexdigest(),
                "messageDigest": hashlib.sha256(prompt.encode()).hexdigest(), "baselineMessageIds": []}
        receipt = {"threadId": harness.thread_id, "target": target, "sessionId": "gc-session",
                   "create": {"request_id": "gc-create", "event_cursor": "1"}, "turn": turn}
        (receipts / (hashlib.sha256(harness.thread_id.encode()).hexdigest() + ".json")).write_text(json.dumps(receipt))
        provider_id = "gcs1_" + base64.urlsafe_b64encode(json.dumps({"v": 1, "target": target,
                                                                   "sessionId": "gc-session"}).encode()).decode().rstrip("=")
        return harness, prompt, provider_id

    def test_personal_receipt_bypasses_binding_only_after_live_global_config_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness, prompt, provider_id = self.harness(Path(tmp).resolve())
            requests = []
            def respond(request, timeout):
                requests.append(request.full_url)
                if request.full_url.endswith("/config"):
                    data = {"agents": [{"name": "global"}]}
                elif "/transcript?" in request.full_url:
                    data = {"schema_version": "session.structured.v1", "history": {"tail_state": {"activity": "idle"}},
                            "structured_messages": [{"id": "new-user", "role": "user", "user_prompt": {"text": prompt}}]}
                else:
                    data = {"id": "gc-session", "template": "global", "work_dir": str(harness.workspace)}
                return io.BytesIO(json.dumps(data).encode())
            with patch("live_assertions.urllib.request.build_opener") as build_opener:
                build_opener.return_value.open.side_effect = respond
                harness.verify_gc_prompt(prompt, provider_id)
            self.assertEqual(requests[0], "http://127.0.0.1:12345/v0/city/test-city/config")
            self.assertEqual(len(requests), 3)
            self.assertIn("turn-1-independent-full-forwarded-prompt", harness.report["assertions"])

    def test_unbound_mapped_project_cannot_pass_independent_gc_verification(self):
        with tempfile.TemporaryDirectory() as tmp:
            harness, prompt, provider_id = self.harness(Path(tmp).resolve(), project="project-sample", agent="sample/rig")
            with patch("live_assertions.urllib.request.build_opener") as build_opener:
                with self.assertRaisesRegex(AcceptanceFailure, "exact BB project"):
                    harness.verify_gc_prompt(prompt, provider_id)
                build_opener.assert_not_called()


class ResumeIdentityTests(unittest.TestCase):
    def test_provider_reset_cannot_pass_with_same_gc_session(self):
        before = {"history": {"gc_session_id": "gc-213", "logical_conversation_id": "gc-213",
                              "provider_session_id": "original-conversation", "transcript_stream_id": "original-stream"}}
        verify_resume_identity(before, copy.deepcopy(before))
        for field in before["history"]:
            with self.subTest(field=field):
                after = copy.deepcopy(before)
                after["history"][field] = "replacement"
                with self.assertRaisesRegex(AcceptanceFailure, "identity"):
                    verify_resume_identity(before, after)

    def test_absent_identity_is_not_evidence_of_resume(self):
        with self.assertRaisesRegex(AcceptanceFailure, "identity"):
            verify_resume_identity({"history": {}}, {"history": {}})


class AcceptanceGuardTests(unittest.TestCase):
    def test_resume_memory_cannot_pass_after_reading_a_tool_artifact(self):
        events = completed_events()
        tool = copy.deepcopy(events[3])
        tool["seq"] = 5
        events[-1]["seq"] = 6
        tool["data"]["item"] = {"type": "toolCall", "status": "completed", "name": "Read"}
        events.insert(4, tool)
        with self.assertRaisesRegex(AcceptanceFailure, "without tools"):
            self.run_guard(events, forbid_tools=True)

    def run_guard(self, events, **kwargs):
        # Exercise the real event parser and acceptance decision, without starting
        # any server or pretending these synthetic rows are inference evidence.
        harness = object.__new__(LiveAssertions)
        harness.timeout = 1
        harness.thread_id = "test-thread"
        harness.model = "exact-agent"
        harness.report = kwargs.pop("report", {"turns": []})
        output = kwargs.pop("output", "TEST_MARKER")

        def command(*args):
            return {"output": output} if args[1] == "output" else copy.deepcopy(events)

        with patch.object(harness, "command", side_effect=command), \
                patch.object(harness, "progress"), \
                patch("live_assertions.time.monotonic", side_effect=[0, 0, 0, 2]), \
                patch("live_assertions.time.sleep"):
            return harness.await_turn(after=kwargs.pop("after", 0), expected=kwargs.pop("expected", "TEST_MARKER"), **kwargs)

    def test_correlated_completed_response_is_accepted(self):
        self.assertEqual(self.run_guard(completed_events()), (5, "test-gc-session"))

    def test_explanation_before_final_marker_is_accepted(self):
        events = completed_events()
        text = "Verified the requested file.\n\nTEST_MARKER"
        events[3]["data"]["item"]["text"] = text
        self.assertEqual(self.run_guard(events, output=text), (5, "test-gc-session"))

    def test_embedded_or_nonfinal_marker_cannot_pass(self):
        for text in ["Not TEST_MARKER", "TEST_MARKER\nSomething else"]:
            with self.subTest(text=text):
                events = completed_events()
                events[3]["data"]["item"]["text"] = text
                with self.assertRaisesRegex(AcceptanceFailure, "Fresh final assistant"):
                    self.run_guard(events, output=text)

    def test_marker_mismatch_reports_only_safe_diagnostics_and_still_fails(self):
        expected = "BEGIN_private END_private"
        for text, first, last, line in [
            ("  private-answer café\n", False, False, False),
            ("BEGIN_private private-answer", True, False, False),
            ("private-answer END_private", False, True, False),
            (expected + "\nprivate-answer", True, True, True),
        ]:
            with self.subTest(text=text):
                events = completed_events()
                events[3]["data"]["item"]["text"] = text
                report = {"turns": []}
                with self.assertRaisesRegex(AcceptanceFailure, "Fresh final assistant"):
                    self.run_guard(events, expected=expected, report=report)
                self.assertEqual(report["turns"], [])
                self.assertEqual(report["marker_mismatch"], {
                    "output_bytes": len(text.encode()),
                    "output_sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "first_expected_token_present": first,
                    "last_expected_token_present": last,
                    "expected_line_present": line,
                })
                serialized = json.dumps(report)
                for private in (text, expected, "private-answer", "BEGIN_private", "END_private"):
                    self.assertNotIn(private, serialized)

    def test_missing_answer_reports_empty_output_without_passing(self):
        events = completed_events()
        del events[3]
        report = {"turns": []}
        with self.assertRaisesRegex(AcceptanceFailure, "Fresh final assistant"):
            self.run_guard(events, report=report)
        self.assertEqual(report["marker_mismatch"]["output_bytes"], 0)
        self.assertEqual(report["marker_mismatch"]["output_sha256"], hashlib.sha256(b"").hexdigest())
        self.assertFalse(report["marker_mismatch"]["expected_line_present"])

    def test_marker_without_terminal_event_times_out(self):
        with self.assertRaisesRegex(AcceptanceFailure, "No verified BB completion"):
            self.run_guard(completed_events()[:-1])

    def test_failed_turn_cannot_pass_with_correct_answer(self):
        events = completed_events()
        events[-1]["data"]["status"] = "failed"
        with self.assertRaisesRegex(AcceptanceFailure, "failed status"):
            self.run_guard(events)

    def test_wrong_model_cannot_pass_with_correct_answer(self):
        events = completed_events()
        events[0]["data"]["execution"]["model"] = "different-agent"
        with self.assertRaisesRegex(AcceptanceFailure, "exact requested model"):
            self.run_guard(events)

    def test_stale_first_turn_cannot_satisfy_second_turn(self):
        with self.assertRaisesRegex(AcceptanceFailure, "No verified BB completion"):
            self.run_guard(completed_events(), after=5)

    def test_wrong_accepted_request_cannot_pass(self):
        events = completed_events()
        events[2]["data"]["clientRequestId"] = "different-request"
        with self.assertRaisesRegex(AcceptanceFailure, "not correlated"):
            self.run_guard(events)

    def test_tool_turn_without_tool_event_cannot_pass(self):
        with self.assertRaisesRegex(AcceptanceFailure, "completed tool call"):
            self.run_guard(completed_events(), require_tool=True)

    def test_second_turn_must_keep_gc_identity(self):
        with self.assertRaisesRegex(AcceptanceFailure, "identity missing or changed"):
            self.run_guard(completed_events(), previous_provider_id="another-session")


class IndependentTranscriptGuardTests(unittest.TestCase):
    def setUp(self):
        self.prompt = "Reply TEST_MARKER"
        self.forwarded = "BB session context:\n" + "context " * 200 + "\nUser request:\n" + self.prompt
        self.turn = {"messageDigest": hashlib.sha256(self.forwarded.encode()).hexdigest(),
                     "baselineMessageIds": ["earlier-user"]}
        self.frame = {"schema_version": "session.structured.v1", "history": {"tail_state": {
            "activity": "idle", "degraded": False, "open_tool_call_ids": [], "pending_interaction_ids": []}},
            "structured_messages": [{"id": "new-user", "role": "user", "status": "final",
                                     "user_prompt": {"text": self.forwarded}, "blocks": []}]}

    def test_complete_forwarded_prompt_is_required(self):
        self.assertEqual(verify_prompt_frame(self.frame, self.turn, self.prompt)["forwarded_prompt_sha256"],
                         self.turn["messageDigest"])

    def test_released_gc_omits_false_degraded_field(self):
        del self.frame["history"]["tail_state"]["degraded"]
        self.assertEqual(verify_prompt_frame(self.frame, self.turn, self.prompt)["forwarded_prompt_sha256"],
                         self.turn["messageDigest"])

    def test_user_marker_surviving_wrapper_truncation_cannot_pass(self):
        self.frame["structured_messages"][0]["user_prompt"]["text"] = self.forwarded[1024:]
        self.assertIn(self.prompt, self.frame["structured_messages"][0]["user_prompt"]["text"])
        with self.assertRaisesRegex(AcceptanceFailure, "complete forwarded prompt"):
            verify_prompt_frame(self.frame, self.turn, self.prompt)

    def test_missing_user_entry_cannot_pass(self):
        self.frame["structured_messages"] = []
        with self.assertRaisesRegex(AcceptanceFailure, "new user entry"):
            verify_prompt_frame(self.frame, self.turn, self.prompt)

    def test_matching_old_prompt_cannot_pass(self):
        self.frame["structured_messages"][0]["id"] = "earlier-user"
        with self.assertRaisesRegex(AcceptanceFailure, "new user entry"):
            verify_prompt_frame(self.frame, self.turn, self.prompt)

    def test_duplicate_delivery_cannot_pass(self):
        duplicate = copy.deepcopy(self.frame["structured_messages"][0])
        duplicate["id"] = "duplicate-user"
        self.frame["structured_messages"].append(duplicate)
        with self.assertRaisesRegex(AcceptanceFailure, "exactly one"):
            verify_prompt_frame(self.frame, self.turn, self.prompt)

    def test_unknown_activity_and_degraded_history_cannot_pass(self):
        for update in ({"activity": "unknown"}, {"degraded": True}):
            with self.subTest(update=update):
                frame = copy.deepcopy(self.frame)
                frame["history"]["tail_state"].update(update)
                with self.assertRaisesRegex(AcceptanceFailure, "reliably idle"):
                    verify_prompt_frame(frame, self.turn, self.prompt)

    def test_open_tools_cannot_pass(self):
        self.frame["history"]["tail_state"]["open_tool_call_ids"] = ["tool-in-flight"]
        with self.assertRaisesRegex(AcceptanceFailure, "pending tools"):
            verify_prompt_frame(self.frame, self.turn, self.prompt)

    def test_failure_classification_never_discloses_provider_text(self):
        self.assertEqual(safe_provider_failure({"message": "private-secret complete submitted prompt"}),
                         "GC did not preserve the complete forwarded prompt")
        self.assertEqual(safe_provider_failure({"message": "private-secret reliable turn activity"}),
                         "GC runtime activity or structured history is unreliable")
        self.assertEqual(safe_provider_failure({"message": "private-secret session is busy"}),
                         "GC session is busy or waiting for a response")
        self.assertNotIn("private-secret", safe_provider_failure({"message": "private-secret"}))


if __name__ == "__main__":
    unittest.main()
