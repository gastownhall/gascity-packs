import copy
import json
from pathlib import Path
import tempfile
import tomllib
import unittest

from codex_hook_trust import CODEX_VERSION, expected_hooks, trust_config, verify_gc_hooks, verify_launch


class CodexHookTrustTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="bb-hook-review-")
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        (self.workspace / ".codex").mkdir()
        self.hooks = self.workspace / ".codex/hooks.json"
        self.hooks.write_text(json.dumps(expected_hooks()))

    def test_accepts_only_reviewed_gc_hooks(self):
        self.assertEqual(verify_gc_hooks(self.workspace), expected_hooks())

    def test_rejects_changed_or_extra_hooks(self):
        for mutation in ("command", "matcher", "event", "handler", "metadata"):
            with self.subTest(mutation=mutation):
                payload = copy.deepcopy(expected_hooks())
                group = payload["hooks"]["SessionStart"][0]
                if mutation == "command":
                    group["hooks"][0]["command"] += " && unexpected-command"
                elif mutation == "matcher":
                    group["matcher"] = "resume"
                elif mutation == "event":
                    payload["hooks"]["Stop"] = copy.deepcopy([group])
                elif mutation == "handler":
                    group["hooks"].append(copy.deepcopy(group["hooks"][0]))
                else:
                    group["hooks"][0]["async"] = True
                self.hooks.write_text(json.dumps(payload))
                with self.assertRaisesRegex(ValueError, "reviewed"):
                    verify_gc_hooks(self.workspace)

    def test_native_trust_is_bound_to_exact_workspace_and_version(self):
        state = tomllib.loads(trust_config([self.workspace], CODEX_VERSION))["hooks"]["state"]
        self.assertEqual(len(state), 4)
        key = f"{self.workspace.resolve()}/.codex/hooks.json:session_start:0:0"
        self.assertEqual(state[key], {"trusted_hash": "sha256:10ff376f8efe2e535077b7600c0cda5dea8539e872fa2ca1f0e8a5455c50fdf6"})
        with self.assertRaisesRegex(ValueError, "0.153.4"):
            trust_config([self.workspace], "codex-cli 0.154.0")

    def test_launch_requires_expected_workspace_and_codex_home(self):
        home = self.workspace / "private-codex-home"
        env = {"CODEX_HOME": str(home)}
        verify_launch(self.workspace, home, [self.workspace], env)
        with self.assertRaisesRegex(ValueError, "workspaces"):
            verify_launch(self.workspace.parent, home, [self.workspace], env)
        for wrong_env in ({}, {"CODEX_HOME": str(self.workspace / "other")}):
            with self.assertRaisesRegex(ValueError, "CODEX_HOME"):
                verify_launch(self.workspace, home, [self.workspace], wrong_env)

    def test_rejects_symlinked_source(self):
        other = self.workspace / "other.json"
        other.write_text(json.dumps(expected_hooks()))
        self.hooks.unlink()  # this test's disposable fixture only
        self.hooks.symlink_to(other)
        with self.assertRaisesRegex(ValueError, "regular files"):
            verify_gc_hooks(self.workspace)


if __name__ == "__main__":
    unittest.main()
