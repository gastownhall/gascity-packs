"""Exercise installer/launcher entrypoints with isolated npm and BB processes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

PACK = Path(__file__).resolve().parents[1]


class InstallerIntegration(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="bb-installer-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.source = self.root / "pack" / "assets" / "plugin"
        (self.source / "src").mkdir(parents=True)
        for name in ["package.json", "package-lock.json", "tsconfig.json"]:
            (self.source / name).write_text('{"name":"bb-plugin-gas-city","version":"0.1.0"}')
        for name in ["server.ts", "host.ts", "app.tsx", "src/cli.ts"]:
            (self.source / name).write_text("new source")
        self.install = self.root / "installed"
        self.install.mkdir()
        (self.install / "server.ts").write_text("operator edits")
        (self.install / "dist").mkdir()
        (self.install / "dist" / "cli.js").write_text('console.log("legacy CLI");')
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.stub("npm", '''#!/bin/sh
set -eu
if [ "$1" = ci ]; then
  [ "${FAIL_NPM:-}" != ci ] || exit 23
else
  [ "${FAIL_NPM:-}" != build ] || exit 24
  mkdir -p dist
  printf 'console.log("new CLI");' > dist/cli.js
fi
''')
        self.stub("bb", '''#!/usr/bin/env python3
import json, os, pathlib, sys
root = pathlib.Path(os.environ['STUB_ROOT'])
state = root / 'registration.json'
args = sys.argv[1:]
with (root / 'bb-calls.jsonl').open('a') as f: f.write(json.dumps(args)+'\\n')
if args == ['plugin', 'list', '--json']:
    print(json.dumps({'plugins': [json.loads(state.read_text())] if state.exists() else []}))
elif args[:2] == ['plugin', 'install']:
    source = args[2]
    status = 'error' if os.environ.get('FAIL_BB') == 'status' and '/versions/' in source else 'running'
    state.write_text(json.dumps({'id':'gas-city','source':source,'rootDir':source[5:],'status':status,'enabled':True}))
    if os.environ.get('FAIL_BB') == 'exit' and '/versions/' in source: sys.exit(25)
else: sys.exit('unexpected BB operation '+repr(args))
''')
        self.env = dict(os.environ, PATH=str(self.bin)+os.pathsep+os.environ["PATH"],
                        GC_PACK_DIR=str(self.source.parents[1]), GC_BB_INSTALL_DIR=str(self.install),
                        STUB_ROOT=str(self.root))

    def stub(self, name, text):
        path = self.bin / name
        path.write_text(text)
        path.chmod(0o755)

    def run_install(self, **env):
        return subprocess.run([str(PACK / "commands/install/run.sh"), "--yes"],
                              env=dict(self.env, **env), text=True, capture_output=True, timeout=15)

    def test_success_preserves_legacy_sources_and_activates_complete_new_version(self):
        result = self.run_install()
        self.assertEqual(result.returncode, 0, result.stderr+result.stdout)
        self.assertEqual((self.install / "server.ts").read_text(), "operator edits")
        active = (self.install / "current").resolve()
        self.assertNotEqual(active, self.install)
        self.assertEqual((active / "app.tsx").read_text(), "new source")
        launch = subprocess.run([str(PACK / "assets/run-cli.sh"), "status"],
                                env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(launch.returncode, 0, launch.stderr)
        self.assertEqual(launch.stdout.strip(), "new CLI")

    def test_failed_registration_restores_previous_source_without_uninstall(self):
        previous = {"id":"gas-city", "source":"path:"+str(self.install),
                    "rootDir":str(self.install), "status":"running", "enabled":True}
        (self.root / "registration.json").write_text(json.dumps(previous))
        settings = self.root / "plugin-settings.json"
        settings.write_text('{"secret":"preserve"}')
        result = self.run_install(FAIL_BB="status")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads((self.root / "registration.json").read_text()), previous)
        self.assertFalse((self.install / "current").exists())
        self.assertEqual((self.install / "server.ts").read_text(), "operator edits")
        self.assertEqual(settings.read_text(), '{"secret":"preserve"}')
        calls = [json.loads(line) for line in (self.root / "bb-calls.jsonl").read_text().splitlines()]
        self.assertFalse(any("remove" in call or "uninstall" in call for call in calls))
        self.assertEqual(sum(call[:2] == ["plugin", "install"] for call in calls), 2)

    def test_dependency_and_build_failures_do_not_activate_or_register(self):
        for failure in ["ci", "build"]:
            with self.subTest(failure=failure):
                result = self.run_install(FAIL_NPM=failure)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.install / "current").exists())
                self.assertFalse((self.root / "registration.json").exists())
                self.assertEqual((self.install / "server.ts").read_text(), "operator edits")
                self.assertIn("retained for inspection", result.stderr)
        self.assertEqual(len(list((self.install / "versions").iterdir())), 2)

    def test_update_preserves_previous_version_and_unknown_user_files(self):
        first = self.run_install()
        self.assertEqual(first.returncode, 0, first.stderr)
        previous = (self.install / "current").resolve()
        (previous / "user-notes.txt").write_text("keep me")
        (previous / "server.ts").write_text("customized install")
        second = self.run_install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual((self.install / "current").resolve(), previous)
        self.assertEqual((previous / "user-notes.txt").read_text(), "keep me")
        self.assertEqual((previous / "server.ts").read_text(), "customized install")
        self.assertEqual(len(list((self.install / "versions").iterdir())), 2)

    def test_current_collision_preserves_user_entry(self):
        (self.install / "current").write_text("user data")
        result = self.run_install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Preserving unexpected", result.stderr)
        self.assertEqual((self.install / "current").read_text(), "user data")
        self.assertFalse((self.root / "registration.json").exists())

    def test_nonzero_bb_exit_after_registration_restores_previous_source(self):
        previous = {"id":"gas-city", "source":"path:"+str(self.install),
                    "rootDir":str(self.install), "status":"running", "enabled":True}
        (self.root / "registration.json").write_text(json.dumps(previous))
        result = self.run_install(FAIL_BB="exit")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Restored previous BB registration", result.stderr)
        self.assertEqual(json.loads((self.root / "registration.json").read_text()), previous)
        self.assertFalse((self.install / "current").exists())

    def test_legacy_install_still_launches_before_migration(self):
        result = subprocess.run([str(PACK / "assets/run-cli.sh"), "status"],
                                env=self.env, text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "legacy CLI")


if __name__ == "__main__":
    unittest.main()
