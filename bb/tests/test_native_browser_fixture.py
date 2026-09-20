"""Fixture isolation guards; synthetic state here is not live acceptance proof."""
import json
import hashlib
from pathlib import Path
import tempfile
import tomllib
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from full_e2e_browser_cases import fixture, native_fixture_evidence, require_empty_native_fixture
from live_assertions import AcceptanceFailure
from runtime_artifact import runtime_artifact


class NativeBrowserFixtureTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        top = Path(self.scratch.name).resolve()
        self.root = top / "owned"
        self.root.mkdir()
        self.city, self.private = self.root / "city", self.root / "private"
        for directory in (self.city / "agents/global", self.private, self.root / "original-config"):
            directory.mkdir(parents=True)
        self.binary = top / "external-native-wrapper"
        self.binary.write_text("#!/bin/sh\nexit 0\n")
        self.binary.chmod(0o700)
        source = self.root / "original-launch.json"
        self.original = {"home_root": "/existing/homes", "session_root": "/existing/transcripts", "pool_id": "native-claude",
                         "claude_binary": str(self.binary), "claude_sha256": hashlib.sha256(self.binary.read_bytes()).hexdigest()}
        source.write_text(json.dumps(self.original))
        (self.root / "original-config/.claude.json").write_text(json.dumps({"projects": {"old": {"hasTrustDialogAccepted": True}}}))
        self.original_city = ('[daemon]\nobserve_paths = ["existing-observation"]\n'
                              '[providers.claude]\ncommand = ' + json.dumps(str(self.binary)) + '\n')
        (self.city / "city.toml").write_text(self.original_city)
        self.runner = SimpleNamespace(root=self.root, private=self.private, runtime="claude",
            env={"PATH": str(top), "CLAUDE_CONFIG_DIR": str(self.root / "original-config"),
                 "MANIFOLD_CLAUDE_LAUNCH_CONFIG": str(source)},
            manifest={"versions": {"claude": "test-version"}, "gcUrl": "http://127.0.0.1:1"},
            agent=lambda _: {"agent": "global", "connection": "local", "city": "test", "provider": "claude"},
            command=lambda *_: "test-version", bb=lambda *_: None)
        self.runner.manifest["runtimeLaunchArtifact"] = runtime_artifact(self.binary, "test-version", self.runner.command)

    def make_fixture(self, **options):
        with patch("full_e2e_browser_cases.shutil.which", return_value=str(self.binary)), patch(
                "full_e2e_browser_cases.read_json", side_effect=lambda _: {"agents": [
                    {"name": path.name} for path in (self.city / "agents").iterdir()]}):
            return fixture(self.runner, **options)

    def test_native_fixture_observes_actual_transcripts_without_seeding_inactive_trust(self):
        result = self.make_fixture(trusted=True)
        native = result["nativeConfiguration"]
        self.assertFalse(result["trusted"])
        self.assertFalse(Path(native["homeRoot"]).exists())
        self.assertTrue(native["memoryIsolation"]["autoMemoryDisabled"])
        self.assertEqual(json.loads((self.root / "original-launch.json").read_text()), self.original)
        config = tomllib.loads((self.city / "city.toml").read_text())
        provider = config["providers"][result["agent"]["agent"]]
        self.assertEqual(provider["env"]["MANIFOLD_CLAUDE_LAUNCH_CONFIG"], native["path"])
        self.assertNotIn("CLAUDE_CONFIG_DIR", provider["env"])
        self.assertEqual(config["daemon"]["observe_paths"], ["existing-observation", native["sessionRoot"]])
        self.assertEqual(list((Path(native["path"]).parent / "runtime-config").iterdir()), [])
        self.assertEqual(next(self.private.glob("*-city-before.toml")).read_text(), self.original_city)

    def test_external_wrapper_must_match_pinned_launch_identity(self):
        self.runner.manifest["runtimeLaunchArtifact"]["sha256"] = "different"
        with self.assertRaisesRegex(AcceptanceFailure, "pinned launch"):
            self.make_fixture()
        self.assertEqual((self.city / "city.toml").read_text(), self.original_city)

    def test_fresh_native_home_and_actual_transcript_evidence_are_required(self):
        result = self.make_fixture(trusted=False)
        require_empty_native_fixture(result)
        native = result["nativeConfiguration"]
        home = Path(native["homeRoot"]) / "session-derived-home"
        home.mkdir(parents=True)
        with self.assertRaisesRegex(AcceptanceFailure, "already has runtime homes"):
            require_empty_native_fixture(result)
        projects = {result["workspace"]: {"hasTrustDialogAccepted": True}}
        (home / ".claude.json").write_text(json.dumps({"projects": projects}))
        transcripts = Path(native["sessionRoot"])
        transcripts.mkdir(parents=True)
        (home / "projects").symlink_to(transcripts, target_is_directory=True)
        frame = {"history": {"provider_session_id": "provider-uuid"}}
        with self.assertRaisesRegex(AcceptanceFailure, "exact observed provider transcript"):
            native_fixture_evidence(self.runner, result, "thread", "fresh", frame)
        (transcripts / "provider-uuid.jsonl").write_text('{"unit_fixture": true}\n')
        proof = native_fixture_evidence(self.runner, result, "thread", "fresh", frame)
        self.assertEqual(proof["projects"], projects)
        self.assertFalse(proof["trustPreseeded"])
        self.assertEqual(proof["home"], str(home))
        self.assertEqual(proof["transcript"], str(transcripts / "provider-uuid.jsonl"))


if __name__ == "__main__":
    unittest.main()
