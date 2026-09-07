"""Load the installed pack through the actual GC 1.4 CLI, without inference."""
import json
import os
from pathlib import Path
import subprocess
import shlex
import shutil
import sys
import tempfile
import unittest

PACK = Path(__file__).resolve().parents[1]

class PackIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gc = os.environ.get("GC_TEST_BIN")
        if not cls.gc:
            raise unittest.SkipTest("Set GC_TEST_BIN to a Gas City 1.4 executable")
        cls.gc = str(Path(cls.gc).resolve())
        cls.scratch = tempfile.TemporaryDirectory(prefix="bb-pack-gc14-")
        cls.root = Path(cls.scratch.name)
        cls.city = cls.root / "city"
        (cls.city / ".gc").mkdir(parents=True)
        (cls.city / "pack.toml").write_text('[pack]\nname = "bb-test"\nschema = 2\n\n[imports.bb]\nsource = '+json.dumps(str(PACK))+'\n')
        (cls.city / "city.toml").write_text('[workspace]\nname = "bb-test"\n\n[providers.claude]\nbase = "builtin:claude"\n')
        cls.env = {k:v for k,v in os.environ.items() if not k.startswith(("GC_", "BEADS_"))}
        cls.env.update({"GC_HOME":str(cls.root/'gc-home'), "GC_DISABLE_USAGE_METRICS":"1", "GC_BB_INSTALL_DIR":str(cls.root/'missing-install'), "GC_BB_CONFIG":str(cls.root/'missing-config')})
    @classmethod
    def tearDownClass(cls):
        cls.scratch.cleanup()
    def run_gc(self, *args):
        return subprocess.run([self.gc, *args], cwd=self.city, env=self.env, text=True, capture_output=True, timeout=30)
    def test_exact_release_and_lint(self):
        version=self.run_gc('version')
        self.assertRegex(version.stdout, r'^1\.4\.')
        result=self.run_gc('lint', str(PACK), '--json')
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertTrue(json.loads(result.stdout)['passed'])
    def test_resolved_config_and_command_discovery(self):
        result=self.run_gc('config','show','--validate')
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        result=self.run_gc('bb','--help')
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        for command in ['install','connect','bind','agents','status','recover']:
            self.assertIn(command,result.stdout)
        result=self.run_gc('bb','bind','--help')
        self.assertEqual(result.returncode,0,result.stderr+result.stdout)
        self.assertIn('--project',result.stdout)
    def test_json_contracts_are_discoverable_in_released_gc(self):
        for command, field in [('agents', 'agents'), ('status', 'registration')]:
            result = self.run_gc('bb', command, '--json-schema=result')
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn(field, json.loads(result.stdout)['properties'])
    def test_uninstalled_adapter_is_an_actionable_failure(self):
        result=self.run_gc('bb','status')
        self.assertNotEqual(result.returncode,0)
        self.assertIn('gc bb install',result.stderr+result.stdout)
    def test_codex_acceptance_wrapper_resolves_and_executes_start_and_resume(self):
        from codex_hook_trust import expected_hooks, write_provider_commands
        with tempfile.TemporaryDirectory(prefix="bb-codex-launch-") as directory:
            root = Path(directory)
            workspace, home = root / "workspace", root / "codex-home"
            (workspace / ".gc").mkdir(parents=True)
            (workspace / ".codex").mkdir()
            home.mkdir()
            (workspace / ".codex/hooks.json").write_text(json.dumps(expected_hooks()))
            (workspace / "pack.toml").write_text('[pack]\nname = "codex-launch-test"\nschema = 2\n')
            fake = root / "fake-codex"
            fake.write_text('#!' + sys.executable + '\nimport json, os, sys\nprint(json.dumps({"args": sys.argv[1:], "cwd": os.getcwd(), "home": os.environ["CODEX_HOME"]}))\n')
            fake.chmod(0o700)
            commands = write_provider_commands(root, fake, home, [workspace])
            (workspace / "city.toml").write_text('[workspace]\nname = "codex-launch-test"\nprovider = "codex"\n[providers.codex]\nbase = "builtin:codex"\n' + commands)
            env = {**self.env, "CODEX_HOME": str(home)}
            def gc(*args):
                return subprocess.run([self.gc, *args], cwd=workspace, env=env, capture_output=True, text=True, timeout=30)
            valid = gc("config", "show", "--validate")
            self.assertEqual(valid.returncode, 0, valid.stdout + valid.stderr)
            explained = gc("config", "explain", "--provider", "codex", "--json")
            self.assertEqual(explained.returncode, 0, explained.stdout + explained.stderr)
            provider = json.loads(explained.stdout)
            self.assertEqual(provider["builtin_ancestor"], "codex")
            resolved = provider["resolved"]
            self.assertEqual(shutil.which(resolved["command"]), str(root / "codex-verified"))
            self.assertTrue(resolved["supports_hooks"])
            self.assertIn("codex", resolved["process_names"])
            self.assertIn("resume", resolved["resume_command"])
            self.assertIn("{{.SessionKey}}", resolved["resume_command"])
            for invocation, extra in (([resolved["command"], *(resolved["args"] or [])], ["--model", "fixture model", "prompt with spaces"]),
                                      (shlex.split(resolved["resume_command"].replace("{{.SessionKey}}", "session-fixture")), [])):
                launched = subprocess.run(invocation + extra, cwd=workspace, env=env, text=True, capture_output=True, timeout=10)
                self.assertEqual(launched.returncode, 0, launched.stderr)
                actual = json.loads(launched.stdout)
                self.assertEqual(actual, {"args": invocation[1:] + extra, "cwd": str(workspace.resolve()), "home": str(home)})
            changed_hooks = expected_hooks()
            changed_hooks["hooks"]["SessionStart"][0]["hooks"][0]["command"] += " && unexpected-command"
            (workspace / ".codex/hooks.json").write_text(json.dumps(changed_hooks))
            blocked = subprocess.run([resolved["command"]], cwd=workspace, env=env, text=True, capture_output=True, timeout=10)
            self.assertNotEqual(blocked.returncode, 0)
            self.assertEqual(blocked.stdout, "")
            self.assertIn("four reviewed GC hooks", blocked.stderr)
            # The former shape failed GC validation and executable resolution.
            old_command = shlex.join([sys.executable, str(PACK / "tests/codex_hook_trust.py"), "--codex-bin", str(fake)])
            self.assertIsNone(shutil.which(old_command))
            (workspace / "city.toml").write_text('[workspace]\nname = "codex-launch-test"\nprovider = "codex"\n[providers.codex]\nbase = "builtin:codex"\ncommand = ' + json.dumps(old_command) + '\n')
            invalid = gc("config", "show", "--validate")
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("resume_command", invalid.stdout + invalid.stderr)

    def test_shell_entrypoints_are_executable(self):
        for path in [*PACK.glob('commands/*/run.sh'),*PACK.glob('doctor/*/run.sh'),PACK/'assets/run-cli.sh']:
            self.assertTrue(os.access(path,os.X_OK),str(path))
            result=subprocess.run(['sh','-n',str(path)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)

if __name__ == '__main__': unittest.main()
