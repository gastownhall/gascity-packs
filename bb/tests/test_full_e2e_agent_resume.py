"""Native restart guards use recorded GC states, without running a model."""
import copy
import base64
import itertools
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from full_e2e import Runner
from live_assertions import AcceptanceFailure, LiveAssertions


class AgentResumeTests(unittest.TestCase):
    def fixture(self, states, *, changed_identity=False):
        frame = {"history": {"tail_state": {"activity": "idle"},
            "gc_session_id": "gc-5", "logical_conversation_id": "conversation",
            "provider_session_id": "native-uuid", "transcript_stream_id": "stream"}}
        harness = SimpleNamespace(thread_id="thread", last_gc_frame=copy.deepcopy(frame))
        remaining = itertools.chain(states, itertools.repeat(states[-1]))
        read = patch("full_e2e.read_json", side_effect=lambda *args: next(remaining))
        read.start(); self.addCleanup(read.stop)
        clock = patch("full_e2e.time.monotonic", side_effect=[0, 0, 0, 46])
        clock.start(); self.addCleanup(clock.stop)
        sleep = patch("full_e2e.time.sleep")
        sleep.start(); self.addCleanup(sleep.stop)

        def fetch(suffix, label, method="GET"):
            if suffix == "/transcript?format=structured": return frame
            if suffix == "/suspend": return {"status": "ok"}
            if suffix == "": return next(remaining)
            raise AssertionError(suffix)

        harness.gc_fetch = Mock(side_effect=fetch)
        identity = "gcs1_" + base64.urlsafe_b64encode(json.dumps({"sessionId": "gc-5"}).encode()).decode().rstrip("=")
        conversation = {"harness": harness, "agent": {"city": "city"}, "identity": identity,
            "project": "project", "workspace": "/workspace", "reasoning": "medium",
            "memory": "private-word", "frame": frame}
        runner = object.__new__(Runner)
        runner.manifest = {"gcUrl": "http://127.0.0.1:1234"}
        runner.conversations = {"native.personal": conversation}
        runner.browser = Mock(return_value={"afterSeq": 10})

        def verify(*args, **kwargs):
            if changed_identity:
                harness.last_gc_frame["history"]["provider_session_id"] = "different-uuid"

        runner.verify_turn = Mock(side_effect=verify)
        return runner, harness, conversation

    def test_both_stopped_states_are_recorded_before_exact_conversation_recall(self):
        for state in ("suspended", "asleep"):
            with self.subTest(state=state):
                runner, harness, conversation = self.fixture([{"state": state, "running": False}])
                result = runner.agent_resume()
                self.assertTrue(result["identity_preserved"])
                harness.gc_fetch.assert_any_call("", "native-suspend-state-0")
                self.assertEqual(runner.browser.call_args.kwargs["thread"], harness.thread_id)
                self.assertEqual(runner.verify_turn.call_args.kwargs,
                                 {"provider": conversation["identity"], "no_tools": True})

    def test_active_running_or_missing_liveness_never_counts_as_stopped(self):
        invalid = [{"state": "active", "running": False},
                   {"state": "asleep", "running": True},
                   {"state": "suspended", "running": True},
                   {"state": "suspended"}, {"state": "suspended", "running": 0}]
        for state in invalid:
            with self.subTest(state=state):
                runner, harness, _ = self.fixture([state])
                with patch("full_e2e.time.monotonic", side_effect=[0, 0, 46]), \
                     patch("full_e2e.time.sleep"), self.assertRaisesRegex(AcceptanceFailure, "never settled"):
                    runner.agent_resume()
                runner.browser.assert_not_called()
                harness.gc_fetch.assert_any_call("", "native-suspend-state-0")

    def test_each_poll_has_a_distinct_evidence_label(self):
        runner, harness, _ = self.fixture([{"state": "suspended", "running": True},
                                         {"state": "suspended", "running": False}])
        with patch("full_e2e.time.sleep"):
            runner.agent_resume()
        harness.gc_fetch.assert_any_call("", "native-suspend-state-0")
        harness.gc_fetch.assert_any_call("", "native-suspend-state-1")

    def test_stopped_state_does_not_bypass_native_identity_check(self):
        runner, _, _ = self.fixture([{"state": "suspended", "running": False}], changed_identity=True)
        with self.assertRaisesRegex(AcceptanceFailure, "changed a conversation"):
            runner.agent_resume()

    def smoke_fixture(self, states, *, changed_identity=False):
        runner, harness, _ = self.fixture(states)
        harness.progress = Mock()
        harness.model = "exact-agent"
        harness.report = {"assertions": [], "prompt_bytes": [], "prompt_sha256": []}
        harness.events = Mock(return_value=[{"seq": 12}])
        harness.command = Mock()
        harness.await_turn = Mock()
        harness.verify_gc_prompt = runner.verify_turn
        if changed_identity:
            harness.verify_gc_prompt = Mock(side_effect=lambda *args:
                harness.last_gc_frame["history"].update(provider_session_id="different-uuid"))
        return harness

    def test_smoke_accepts_both_stopped_states_with_identity_and_no_tools_guards(self):
        for state in ("suspended", "asleep"):
            with self.subTest(state=state):
                harness = self.smoke_fixture([{"state": state, "running": False}])
                LiveAssertions.verify_agent_resume(harness, "exact-provider", "private-word", "nonce")
                harness.gc_fetch.assert_any_call("", "suspend-state-0")
                harness.await_turn.assert_called_once_with(after=12, expected="RESUMED_nonce private-word",
                    previous_provider_id="exact-provider", forbid_tools=True)
                self.assertIn("same-provider-conversation-after-agent-resume", harness.report["assertions"])

    def test_smoke_rejects_unstopped_state_without_submitting(self):
        for state in ({"state": "active", "running": False},
                      {"state": "suspended", "running": True}, {"state": "asleep"}):
            with self.subTest(state=state):
                harness = self.smoke_fixture([state])
                with self.assertRaisesRegex(AcceptanceFailure, "did not settle"):
                    LiveAssertions.verify_agent_resume(harness, "exact-provider", "private-word", "nonce")
                harness.command.assert_not_called()

    def test_smoke_recall_cannot_change_provider_identity(self):
        harness = self.smoke_fixture([{"state": "suspended", "running": False}], changed_identity=True)
        with self.assertRaisesRegex(AcceptanceFailure, "changed a conversation"):
            LiveAssertions.verify_agent_resume(harness, "exact-provider", "private-word", "nonce")


if __name__ == "__main__": unittest.main()
