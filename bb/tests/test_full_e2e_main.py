"""Convenience preparation forwards route, native isolation and exact build identity."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from full_e2e import main


class FullE2EArgumentsTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="bb-e2e-arguments-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.manifest = {"gcCommit": "a" * 40, "modelRoute": "kimi-for-coding",
                         "runtimeArtifact": {"binary": "/pinned/claude", "sha256": "b" * 64}}

    def test_native_development_preparation_retains_all_identity_arguments(self):
        report = self.root / "report"
        options = {"--runtime": "claude", "--gc-bin": "/pinned/gc", "--bb-bin": "/pinned/bb",
            "--bb-app-bin": "/pinned/bb-app", "--gc-commit": "a" * 40,
            "--gc-development-base": "1.4.2", "--claude-native-config": "/private/native.json",
            "--runtime-raw-bin": "/pinned/claude", "--model-route": "kimi-for-coding",
            "--report-dir": str(report), "--timeout": "123", "--channel": "chrome",
            "--cases": "native.personal,reasoning.none"}
        def prepare(command, **kwargs):
            self.assertEqual(kwargs, {"check": True})
            self.assertIn("--prepare-only", command)
            for name, expected in options.items():
                if name in {"--report-dir", "--channel", "--cases"}: continue
                self.assertIn(name, command)
                self.assertEqual(command[command.index(name) + 1], expected)
            directory = Path(command[command.index("--report-dir") + 1])
            self.assertEqual(directory, self.root / "report-prepare")
            directory.mkdir()
            (directory / "environment.json").write_text(json.dumps(self.manifest))
        argv = ["full_e2e.py", *(value for pair in options.items() for value in pair)]
        with patch("sys.argv", argv), patch("full_e2e.subprocess.run", side_effect=prepare) as command, \
             patch("full_e2e.Runner") as runner:
            runner.return_value.run.return_value = 7
            self.assertEqual(main(), 7)
        self.assertEqual(command.call_count, 1)
        runner.assert_called_once_with(self.manifest, report, 123, "chrome")
        runner.return_value.run.assert_called_once_with({"native.personal", "reasoning.none"})

    def test_retained_manifest_is_used_without_repreparing_or_relabeling(self):
        manifest_path = self.root / "environment.json"
        manifest_path.write_text(json.dumps(self.manifest))
        report = self.root / "report"
        with patch("sys.argv", ["full_e2e.py", "--environment-manifest", str(manifest_path),
                "--report-dir", str(report)]), patch("full_e2e.subprocess.run") as command, \
             patch("full_e2e.Runner") as runner:
            runner.return_value.run.return_value = 0
            self.assertEqual(main(), 0)
        command.assert_not_called()
        runner.assert_called_once_with(self.manifest, report, 240, None)
        runner.return_value.run.assert_called_once_with(None)


if __name__ == "__main__": unittest.main()
