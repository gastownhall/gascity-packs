"""Guards and configuration orchestration only; no live provider is certified."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from full_e2e_fault_cases import (FaultCases, case_functions, canonical_config,
                                  require_owned_config, verify_native_completion)
from live_faults import FaultFailure
from live_assertions import AcceptanceFailure


class NativeFaultEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.prompt = "First line\nPreserve this full faulted request"
        self.forwarded = "BB session context\n" + self.prompt
        self.receipt = {"turn": {"baselineMessageIds": ["startup"],
                                  "messageDigest": hashlib.sha256(self.forwarded.encode()).hexdigest()}}
        self.frame = {"schema_version": "session.structured.v1",
                      "history": {"tail_state": {"activity": "idle"}},
                      "structured_messages": [
                          {"id": "prompt", "role": "user", "status": "final", "user_prompt": {"text": self.forwarded}},
                          {"id": "answer", "role": "assistant", "status": "final", "blocks": [{"type": "text", "text": "ACTUAL_MARKER"}]}]}

    def verify(self, frame):
        return verify_native_completion(frame, self.receipt, self.prompt, "ACTUAL_MARKER")

    def test_native_reply_requires_exact_new_prompt_and_successful_final_answer(self):
        self.assertEqual(self.verify(self.frame)["gc_assistant_message_id"], "answer")
        frame = copy.deepcopy(self.frame)
        frame["structured_messages"][0]["user_prompt"]["text"] = "First line"
        with self.assertRaisesRegex(AcceptanceFailure, "complete forwarded prompt"):
            self.verify(frame)

    def test_provider_failure_after_a_marker_is_not_success(self):
        frame = copy.deepcopy(self.frame)
        frame["structured_messages"].append({"id": "failure", "role": "system", "status": "final",
                                            "system_event": {"kind": "error", "category": "provider_error"}})
        with self.assertRaisesRegex(FaultFailure, "no settled successful"):
            self.verify(frame)

    def test_streaming_answer_or_marker_followed_by_other_text_fails(self):
        frame = copy.deepcopy(self.frame)
        frame["structured_messages"][1]["status"] = "streaming"
        with self.assertRaisesRegex(FaultFailure, "no settled successful"):
            self.verify(frame)
        frame["structured_messages"][1]["status"] = "final"
        frame["structured_messages"][1]["blocks"][0]["text"] += "\nFailed afterwards"
        with self.assertRaisesRegex(FaultFailure, "final marker"):
            self.verify(frame)


class FaultRoutingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bb-live-", dir="/tmp")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / ".bb-full-e2e-owned.json").write_text(json.dumps({"root": str(self.root)}))
        env = {key: str(self.root / key.lower()) for key in ("GC_HOME", "BB_DATA_DIR", "GC_BB_CONFIG", "XDG_STATE_HOME")}
        env["GC_BB_INSTALL_DIR"] = str(self.root / "install")
        cli = self.root / "install/current/dist/cli.js"
        cli.parent.mkdir(parents=True)
        cli.write_text("// unit fixture only")
        self.config = {"version": 1, "workspacePolicy": "require-match",
                       "connections": [{"id": "local", "url": "http://127.0.0.1:12345"},
                                       {"id": "another", "url": "http://127.0.0.1:23456"}],
                       "bindings": [{"projectId": "preserved", "connection": "another", "city": "other",
                                     "rig": "rig", "paths": [str(self.root / "preserved")]}]}
        Path(env["GC_BB_CONFIG"]).write_text(json.dumps(self.config))
        private = self.root / "private"
        private.mkdir()
        self.agent = {"v": 1, "connection": "local", "city": "city", "agent": "global", "id": "test-model"}
        self.runner = SimpleNamespace(root=self.root, private=private, env=env,
            manifest={"gcUrl": "http://127.0.0.1:12345", "workspaces": {"global": str(self.root / "workspace")}},
            agent=lambda scope: self.agent, command=self.command)
        self.commands = []

    def command(self, *args):
        self.commands.append(args)
        self.assertEqual(args[2:4], ("connect", "--id"))
        path = Path(self.runner.env["GC_BB_CONFIG"])
        config = json.loads(path.read_text())
        connection_id, url = args[4], args[6]
        config["connections"] = [row for row in config["connections"] if row["id"] != connection_id] + [{"id": connection_id, "url": url}]
        path.write_text(json.dumps(config))
        return "fixture changed isolated connection"

    def test_marked_scope_is_required_before_config_mutation(self):
        self.assertEqual(require_owned_config(self.runner), Path(self.runner.env["GC_BB_CONFIG"]))
        self.runner.env["GC_BB_CONFIG"] = str(self.root.parent / "normal-config.json")
        with self.assertRaisesRegex(FaultFailure, "inside the isolated"):
            require_owned_config(self.runner)
        self.assertEqual(self.commands, [])

    def test_existing_settings_and_config_evidence_survive_case_failure(self):
        proxies = []
        class FakeProxy:
            def __init__(self, *args, **kwargs):
                self.url, self.closed = "http://127.0.0.1:34567", False
                proxies.append(self)
            def close(self):
                self.closed = True
        cases = FaultCases(self.runner)
        with patch("full_e2e_fault_cases.FaultProxy", FakeProxy):
            with self.assertRaisesRegex(RuntimeError, "model failed"):
                with cases.routed("failure-test"):
                    current = json.loads(Path(self.runner.env["GC_BB_CONFIG"]).read_text())
                    self.assertEqual(next(row["url"] for row in current["connections"] if row["id"] == "local"), proxies[0].url)
                    self.assertEqual(current["bindings"], self.config["bindings"])
                    raise RuntimeError("model failed")
        current = json.loads(Path(self.runner.env["GC_BB_CONFIG"]).read_text())
        self.assertEqual(canonical_config(current), canonical_config(self.config))
        self.assertTrue(proxies[0].closed)
        self.assertEqual(len(self.commands), 2)
        captured = json.loads((self.runner.private / "failure-test/config-before.json").read_text())
        self.assertEqual(captured, self.config)

    def test_cleanup_failure_retains_proxy_instead_of_abandoning_configured_endpoint(self):
        proxies = []
        class FakeProxy:
            def __init__(self, *args, **kwargs):
                self.url, self.closed = "http://127.0.0.1:34567", False
                proxies.append(self)
            def close(self):
                self.closed = True
        cases = FaultCases(self.runner)
        original = self.runner.command
        def fail_restore(*args):
            if args[-1] == self.config["connections"][0]["url"]:
                raise RuntimeError("restore command failed")
            return original(*args)
        self.runner.command = fail_restore
        with patch("full_e2e_fault_cases.FaultProxy", FakeProxy):
            with self.assertRaisesRegex(RuntimeError, "restore command failed"):
                with cases.routed("restore-failure"):
                    pass
        self.assertFalse(proxies[0].closed)
        self.assertEqual(self.runner.retained_fault_proxies, proxies)

    def test_declared_cases_are_independent_and_registration_does_not_mutate_services(self):
        cases = case_functions(self.runner)
        self.assertEqual(set(cases), {"fault.create_response", "fault.submit_response", "fault.stream_disconnect", "fault.bridge_uncertain_delivery"})
        self.assertTrue(all(callable(case) for case in cases.values()))
        self.assertEqual(self.commands, [])


if __name__ == "__main__":
    unittest.main()
