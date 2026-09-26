"""Exercise lifecycle isolation using real task-created child processes only."""

import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

from live_lifecycle import LifecycleFailure, OwnedProcess


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.state = self.root / "state"
        self.state.mkdir()
        self.sentinel = self.state / "existing-user-like-evidence.txt"
        self.sentinel.write_text("preserve all generations\n")
        self.env = {**os.environ, "TEST_STATE_DIR": str(self.state), "TEST_FINGERPRINT": "retained-value"}
        script = ("import json,os,time; "
                  "print(json.dumps({'cwd':os.getcwd(),'state':os.environ['TEST_STATE_DIR'],"
                  "'value':os.environ['TEST_FINGERPRINT']}),flush=True); time.sleep(300)")
        self.argv = [sys.executable, "-u", "-c", script]
        self.owned = self.make()
        self.addCleanup(self.cleanup_child)

    def make(self, **overrides):
        args = {"scratch_root": self.root, "cwd": self.workspace, "env": self.env,
                "isolated_paths": {"TEST_STATE_DIR": str(self.state)}, "artifacts": self.root / "process-evidence"}
        args.update(overrides)
        return OwnedProcess("fixture-worker", self.argv, **args)

    def cleanup_child(self):
        if self.owned.process and self.owned.process.poll() is None:
            self.owned.interrupt(self.owned.identity, crash=True, timeout=2)
        self.owned.close_evidence()

    def await_log(self, generation):
        path = self.owned.artifacts / f"generation-{generation:03d}.log"
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            data = path.read_text()
            if data.endswith("\n"):
                return data
            time.sleep(0.02)
        self.fail("Fixture child did not emit its startup identity")

    def test_restart_retains_cwd_environment_and_prior_logs(self):
        first = self.owned.start()
        first_bytes = self.await_log(1)
        self.owned.interrupt(first, timeout=2)
        second = self.owned.start()
        second_bytes = self.await_log(2)
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])
        self.assertEqual(first["configuration_sha256"], second["configuration_sha256"])
        self.assertEqual(first_bytes, second_bytes)
        observed = json.loads(second_bytes)
        self.assertEqual(observed, {"cwd": str(self.workspace), "state": str(self.state), "value": "retained-value"})
        self.assertEqual((self.owned.artifacts / "generation-001.log").read_text(), first_bytes)
        self.assertEqual(self.sentinel.read_text(), "preserve all generations\n")
        self.owned.interrupt(second, crash=True, timeout=2)
        events = [json.loads(line) for line in (self.owned.artifacts / "events.jsonl").read_text().splitlines()]
        self.assertEqual([row["action"] for row in events], ["started", "signal", "exited"] * 2)
        self.assertEqual(events[-2]["signal"], "SIGKILL")

    def test_foreign_stale_and_duplicate_actions_are_refused(self):
        first = self.owned.start()
        self.await_log(1)
        with self.assertRaisesRegex(LifecycleFailure, "second live"):
            self.owned.start()
        with self.assertRaisesRegex(LifecycleFailure, "stale, foreign"):
            self.owned.interrupt({**first, "pid": os.getpid()}, crash=True)
        self.assertIsNone(self.owned.snapshot()["returncode"])
        self.owned.interrupt(first, timeout=2)
        self.owned.start()
        self.await_log(2)
        with self.assertRaisesRegex(LifecycleFailure, "stale, foreign"):
            self.owned.interrupt(first)
        self.assertIsNone(self.owned.snapshot()["returncode"])

    def test_state_path_or_cwd_outside_scratch_is_refused(self):
        with self.assertRaisesRegex(LifecycleFailure, "cwd"):
            self.make(cwd=self.root.parent)
        with self.assertRaisesRegex(LifecycleFailure, "state path"):
            self.make(env={**self.env, "TEST_STATE_DIR": str(self.root.parent)},
                      isolated_paths={"TEST_STATE_DIR": str(self.root.parent)})

    def test_restart_cannot_silently_change_environment(self):
        first = self.owned.start()
        self.await_log(1)
        self.owned.interrupt(first, timeout=2)
        self.owned.env["TEST_FINGERPRINT"] = "changed"
        with self.assertRaisesRegex(LifecycleFailure, "changed command"):
            self.owned.start()


if __name__ == "__main__":
    unittest.main()
