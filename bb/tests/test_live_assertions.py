"""Unit checks for acceptance guards; these do not run or certify a model."""

import copy
import hashlib
import unittest
from unittest.mock import patch

from live_assertions import AcceptanceFailure, LiveAssertions, safe_provider_failure, verify_prompt_frame


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


class AcceptanceGuardTests(unittest.TestCase):
    def run_guard(self, events, **kwargs):
        # Exercise the real event parser and acceptance decision, without starting
        # any server or pretending these synthetic rows are inference evidence.
        harness = object.__new__(LiveAssertions)
        harness.timeout = 1
        harness.thread_id = "test-thread"
        harness.model = "exact-agent"
        harness.report = {"turns": []}

        def command(*args):
            return {"output": "TEST_MARKER"} if args[1] == "output" else copy.deepcopy(events)

        with patch.object(harness, "command", side_effect=command), \
                patch.object(harness, "progress"), \
                patch("live_assertions.time.monotonic", side_effect=[0, 0, 0, 2]), \
                patch("live_assertions.time.sleep"):
            return harness.await_turn(after=kwargs.pop("after", 0), expected="TEST_MARKER", **kwargs)

    def test_correlated_completed_response_is_accepted(self):
        self.assertEqual(self.run_guard(completed_events()), (5, "test-gc-session"))

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
