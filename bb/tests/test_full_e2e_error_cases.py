"""Error-evidence guards, not claims that live providers passed."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from live_assertions import AcceptanceFailure
from full_e2e_error_cases import case_functions, error_fixture, require_bb_failure, require_error_delivery
from runtime_artifact import runtime_artifact, verified_runtime_artifact


class ErrorEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.rows = [
            {"seq": 1, "type": "client/turn/requested", "data": {"requestId": "request-one", "execution": {"model": "exact-agent"}}},
            {"seq": 2, "type": "turn/completed", "scope": {"kind": "turn", "turnId": "turn-one"},
             "data": {"status": "failed", "error": {"message": "Incorrect API key provided"}}},
        ]

    def check(self, rows, mode="provider"):
        return require_bb_failure(rows, mode=mode, model="exact-agent")

    def test_error_requires_correct_provider_request_and_relevant_failure(self):
        self.assertEqual(self.check(self.rows)["expected_error"], "Incorrect API key provided")
        rows = copy.deepcopy(self.rows)
        rows[0]["data"]["execution"]["model"] = "fallback-agent"
        with self.assertRaisesRegex(AcceptanceFailure, "selected agent"):
            self.check(rows)
        rows = copy.deepcopy(self.rows)
        rows[1]["data"]["error"]["message"] = "No reliable idle transcript within 150 seconds"
        with self.assertRaisesRegex(AcceptanceFailure, "provider error"):
            self.check(rows)
        rows[1]["data"]["error"]["message"] = "Gas City create failed: session is closed: gc-401"
        with self.assertRaisesRegex(AcceptanceFailure, "provider error"):
            self.check(rows)

    def test_success_or_duplicate_request_cannot_certify_an_error(self):
        rows = copy.deepcopy(self.rows)
        rows.append({"seq": 3, "type": "turn/completed", "data": {"status": "completed"}})
        with self.assertRaisesRegex(AcceptanceFailure, "successful"):
            self.check(rows)
        rows = copy.deepcopy(self.rows)
        rows.insert(1, {"seq": 2, "type": "client/turn/requested", "data": rows[0]["data"]})
        with self.assertRaisesRegex(AcceptanceFailure, "exactly one"):
            self.check(rows)

    def test_native_claude_invalid_oauth_token_error_is_a_provider_failure(self):
        message = "Please run /login · API Error: 401 OAuth access token is invalid."
        rows = copy.deepcopy(self.rows)
        rows[1]["data"]["error"]["message"] = message
        self.assertEqual(self.check(rows)["expected_error"], message)

    def test_provider_failure_requires_native_error_and_exactly_one_whole_prompt(self):
        prompt = "Preserve this entire\nprovider-error request"
        forwarded = "BB context\n" + prompt
        receipt = {"turn": {"baselineMessageIds": ["startup"],
                            "messageDigest": hashlib.sha256(forwarded.encode()).hexdigest()}}
        frame = {"schema_version": "session.structured.v1", "history": {"tail_state": {"activity": "idle"}},
                 "structured_messages": [
                     {"id": "input", "role": "user", "status": "final", "user_prompt": {"text": forwarded}},
                     {"id": "auth-error", "role": "system", "status": "final",
                      "system_event": {"kind": "error", "category": "provider_error", "message": "Incorrect API key provided"}},
                 ]}
        records = [{"operation": "create"}, {"operation": "submit"}]
        self.assertEqual(require_error_delivery("provider", records, receipt, frame, prompt)["submit_requests"], 1)
        wrong = copy.deepcopy(frame)
        wrong["structured_messages"][0]["user_prompt"]["text"] = "Preserve this entire"
        with self.assertRaises(AcceptanceFailure):
            require_error_delivery("provider", records, receipt, wrong, prompt)
        wrong = copy.deepcopy(frame)
        wrong["structured_messages"][-1]["system_event"]["category"] = "provider_retry"
        with self.assertRaisesRegex(AcceptanceFailure, "native provider error"):
            require_error_delivery("provider", records, receipt, wrong, prompt)
        with self.assertRaisesRegex(AcceptanceFailure, "more than once"):
            require_error_delivery("provider", records + [{"operation": "submit"}], receipt, frame, prompt)

    def test_startup_and_timeout_cannot_send_the_user_prompt(self):
        for mode in ("startup", "timeout"):
            self.assertEqual(require_error_delivery(mode, [{"operation": "create"}], {}, None, "never delivered")["submit_requests"], 0)
            with self.assertRaisesRegex(AcceptanceFailure, "before readiness"):
                require_error_delivery(mode, [{"operation": "create"}, {"operation": "submit"}], {}, None, "never delivered")


class ErrorFixtureGuards(unittest.TestCase):
    def test_case_registration_never_launches_or_mutates_anything(self):
        cases = case_functions(object())
        self.assertEqual(set(cases), {"error.provider", "error.startup", "error.timeout"})
        self.assertTrue(all(callable(case) for case in cases.values()))

    def test_codex_fixture_uses_only_new_invalid_credentials_and_preserves_old_config(self):
        from codex_hook_trust import expected_hooks
        with tempfile.TemporaryDirectory(prefix="bb-live-", dir="/var/tmp") as scratch:
            root = Path(scratch).resolve()
            (root / ".bb-full-e2e-owned.json").write_text(json.dumps({"root": str(root)}))
            city, private, binary_dir = root / "city", root / "private", root / "bin"
            for directory in (city / "agents", private, binary_dir): directory.mkdir(parents=True)
            original = '[daemon]\nobserve_paths = []\n[providers.existing]\ncommand = "untouched"\n'
            (city / "city.toml").write_text(original)
            binary = binary_dir / "codex"
            binary.write_text(f'#!{sys.executable}\nimport json, os, sys\n'
                              'if "--version" in sys.argv: print("codex-cli 0.153.4")\n'
                              'else: print(json.dumps({k:os.environ.get(k) for k in '
                              '["CODEX_HOME", "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN"]}))\n')
            binary.chmod(0o700)
            env = {key: str(root / key.lower()) for key in ("GC_HOME", "BB_DATA_DIR", "GC_BB_CONFIG", "XDG_STATE_HOME")}
            env.update(PATH=str(binary_dir), OPENAI_API_KEY="existing-valid-key-must-not-reach-child",
                       ANTHROPIC_API_KEY="existing-other-key", CLAUDE_CODE_OAUTH_TOKEN="existing-oauth")
            calls = []
            runner = SimpleNamespace(root=root, private=private, runtime="codex", env=env,
                manifest={"versions": {"codex": "codex-cli 0.153.4"}, "gcUrl": "http://127.0.0.1:1"},
                agent=lambda scope: {"connection": "local", "city": "city", "agent": "original"},
                command=lambda *args: subprocess.check_output(args, env=env, text=True),
                bb=lambda *args: calls.append(args))
            runner.manifest["runtimeArtifact"] = runtime_artifact(binary, "codex-cli 0.153.4", runner.command)
            class Waiter:
                def __init__(self, _): pass
                def poll(self, _, probe): return probe()
            with patch("full_e2e_error_cases.FaultCases", Waiter), patch("full_e2e_error_cases.read_json",
                    side_effect=lambda _: {"agents": [{"name": p.name} for p in (city / "agents").iterdir()]}):
                fixture = error_fixture(runner, "provider")
            workspace = Path(fixture["workspace"])
            (workspace / ".codex").mkdir()
            (workspace / ".codex/hooks.json").write_text(json.dumps(expected_hooks()))
            runtime = Path(fixture["launchLog"]).parent / "runtime"
            child_env = json.loads(subprocess.check_output([str(runtime)], env=env, cwd=workspace, text=True))
            self.assertEqual(child_env["CODEX_HOME"], fixture["runtimeConfig"])
            self.assertTrue(child_env["OPENAI_API_KEY"].startswith("sk-bb-e2e-intentionally-invalid-"))
            self.assertIsNone(child_env["ANTHROPIC_API_KEY"])
            self.assertIsNone(child_env["CLAUDE_CODE_OAUTH_TOKEN"])
            parsed = tomllib.loads((city / "city.toml").read_text())
            self.assertEqual(parsed["providers"]["existing"], {"command": "untouched"})
            self.assertEqual(next(private.glob("*-city-before.toml")).read_text(), original)
            self.assertEqual(calls, [("plugin", "reload", "gas-city", "--json")])
            self.assertEqual(json.loads(Path(fixture["launchLog"]).read_text())["mode"], "provider")

    def test_claude_error_bypasses_credential_wrapper_and_rechecks_raw_identity(self):
        with tempfile.TemporaryDirectory(prefix="bb-live-", dir="/var/tmp") as scratch:
            root = Path(scratch).resolve()
            (root / ".bb-full-e2e-owned.json").write_text(json.dumps({"root": str(root)}))
            city, private, binary_dir = root / "city", root / "private", root / "bin"
            for directory in (city / "agents", private, binary_dir): directory.mkdir(parents=True)
            (city / "city.toml").write_text('[daemon]\nobserve_paths = []\n')
            wrapper = binary_dir / "claude"
            wrapper.write_text(f'#!{sys.executable}\nraise SystemExit("Credential wrapper must not run")\n')
            wrapper.chmod(0o700)
            raw = binary_dir / "claude-raw"
            raw.write_text(f'#!{sys.executable}\nimport json, os, sys\n'
                           'if "--version" in sys.argv: print("claude-test-version")\n'
                           'else: print(json.dumps({k:os.environ.get(k) for k in '
                           '["CLAUDE_CONFIG_DIR", "CLAUDE_CODE_OAUTH_TOKEN", "ANTHROPIC_AUTH_TOKEN", '
                           '"MANIFOLD_CLAUDE_LAUNCH_CONFIG"]}))\n')
            raw.chmod(0o700)
            env = {key: str(root / key.lower()) for key in ("GC_HOME", "BB_DATA_DIR", "GC_BB_CONFIG", "XDG_STATE_HOME")}
            env.update(PATH=str(binary_dir), ANTHROPIC_AUTH_TOKEN="existing-working-key",
                       MANIFOLD_CLAUDE_LAUNCH_CONFIG="existing-native-launch-config")
            runner = SimpleNamespace(root=root, private=private, runtime="claude", env=env,
                manifest={"versions": {"claude": "claude-test-version"}, "gcUrl": "http://127.0.0.1:1"},
                agent=lambda scope: {"connection": "local", "city": "city", "agent": "original"},
                command=lambda *args: subprocess.check_output(args, env=env, text=True), bb=lambda *args: None)
            with self.assertRaisesRegex(AcceptanceFailure, "pinned raw"):
                verified_runtime_artifact(runner)
            with self.assertRaisesRegex(AcceptanceFailure, "absolute"):
                runtime_artifact("claude-raw", "claude-test-version", runner.command)
            runner.manifest["runtimeArtifact"] = runtime_artifact(raw, "claude-test-version", runner.command)
            class Waiter:
                def __init__(self, _): pass
                def poll(self, _, probe): return probe()
            with patch("full_e2e_error_cases.FaultCases", Waiter), patch("full_e2e_error_cases.read_json",
                    side_effect=lambda _: {"agents": [{"name": p.name} for p in (city / "agents").iterdir()]}):
                fixture = error_fixture(runner, "provider")
            runtime = Path(fixture["launchLog"]).parent / "runtime"
            result = json.loads(subprocess.check_output([str(runtime)], env=env, cwd=fixture["workspace"], text=True))
            self.assertEqual(result["CLAUDE_CONFIG_DIR"], fixture["runtimeConfig"])
            self.assertTrue(result["CLAUDE_CODE_OAUTH_TOKEN"].startswith("sk-ant-oat01-bb-e2e-intentionally-invalid-"))
            self.assertIsNone(result["ANTHROPIC_AUTH_TOKEN"])
            self.assertIsNone(result["MANIFOLD_CLAUDE_LAUNCH_CONFIG"])
            self.assertEqual(fixture["runtimeArtifact"]["path"], str(raw))
            # Only this unit test's throwaway executable is changed.
            with raw.open("a") as stream: stream.write("# changed executable\n")
            with self.assertRaisesRegex(AcceptanceFailure, "differs from the prepared"):
                verified_runtime_artifact(runner)
            changed = subprocess.run([str(runtime)], env=env, capture_output=True, text=True)
            self.assertNotEqual(changed.returncode, 0)
            self.assertIn("changed before launch", changed.stderr)


if __name__ == "__main__":
    unittest.main()
