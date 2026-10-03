"""Artifact guards use disposable files, never a live BB or GC installation."""
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from full_e2e import Runner, file_hash, pack_hash
from live_assertions import AcceptanceFailure


class ArtifactIdentityTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory(prefix="bb-artifact-guards-")
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.here = self.root / "checkout/bb/tests"
        self.here.mkdir(parents=True)
        self.source = self.here.parent / "assets/plugin"
        (self.source / "src").mkdir(parents=True)
        for name, value in {
            "server.ts": "export default {};\n",
            "src/provider.ts": "export const provider = {};\n",
            "package.json": '{"dependencies":{"@get-bb/plugin-sdk":"0.4.47"}}\n',
            "package-lock.json": '{"lockfileVersion":3}\n',
            "tsconfig.json": '{"compilerOptions":{}}\n',
        }.items():
            (self.source / name).write_text(value)
        self.installed = self.root / "isolated/installed-plugin/versions/one"
        shutil.copytree(self.source, self.installed)
        (self.installed / ".gc-bb-install.json").write_text('{"format":1}\n')
        self.current = self.installed.parents[1] / "current"
        self.current.symlink_to(self.installed, target_is_directory=True)
        self.gc = self.root / "gc"
        self.gc.write_text("test-only-gc-binary")
        self.runner = object.__new__(Runner)
        self.runner.root = self.root / "isolated"
        self.runner.runtime = "claude"
        self.runner.env = {"GC_BB_INSTALL_DIR": str(self.current.parent), "BB_DATA_DIR": str(self.runner.root / "bb")}
        self.runner.manifest = {
            "gcUrl": "http://127.0.0.1:54321", "bbUrl": "http://127.0.0.1:54322",
            "commands": {"gc": str(self.gc), "bb": "/fixture/bb"},
            "gcBinarySha256": file_hash(self.gc), "gcCommit": "a" * 40,
            "versions": {"gc": "1.4.2", "bb": "0.43.3", "claude": "2.1.270"},
            "verificationMode": "release",
        }
        self.registration = {"plugins": [{"id": "gas-city", "status": "running", "enabled": True,
            "rootDir": str(self.installed)}]}

    def verify(self):
        def read(url):
            if url.endswith("/health"):
                return {"startup": {"ready": True}, "version": "1.4.2", "build_id": "a" * 12}
            return {"currentVersion": "0.43.3"}
        output = subprocess.CompletedProcess([], 0, json.dumps(self.registration), "")
        with patch("full_e2e.HERE", self.here), patch("full_e2e.read_json", side_effect=read), \
             patch("full_e2e.subprocess.run", return_value=output) as command:
            result = self.runner.verify_artifacts()
        return result, command

    def test_exact_registered_source_including_manifests_passes(self):
        # Generated output is not part of the source identity claim.
        for name in ("dist/cli.js", "node_modules/sdk/index.js"):
            path = self.installed / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("generated")
        result, command = self.verify()
        self.assertEqual(result["pack_sha256"], pack_hash(self.source))
        command.assert_called_once_with(["/fixture/bb", "plugin", "list", "--json"],
            cwd=self.runner.root, env=self.runner.env, capture_output=True, text=True,
            timeout=20, check=True)

    def test_changed_dependency_or_compatibility_manifest_cannot_claim_source_identity(self):
        for name in ("package.json", "package-lock.json", "tsconfig.json"):
            with self.subTest(name=name):
                path = self.installed / name
                original = path.read_bytes()
                path.write_bytes(original + b"changed\n")
                with self.assertRaises(AcceptanceFailure): self.verify()
                path.write_bytes(original)

    def test_model_route_metadata_does_not_relabel_the_actual_cli_runtime(self):
        result, _ = self.verify()
        self.assertNotIn("model_route", result)
        self.runner.manifest["modelRoute"] = "kimi-for-coding"
        result, _ = self.verify()
        self.assertEqual(result["model_route"], "kimi-for-coding")
        self.assertEqual(result["runtime"], "claude")
        self.assertEqual(result["runtime_version"], "2.1.270")

    def test_missing_or_extra_install_source_is_rejected(self):
        original = self.installed / "tsconfig.json"
        moved = self.installed / "unexpected-source.json"
        original.rename(moved)
        with self.assertRaises(AcceptanceFailure): self.verify()

    def test_source_symlink_cannot_hide_an_external_dependency(self):
        outside = self.root / "outside.json"
        outside.write_bytes((self.source / "package.json").read_bytes())
        original = self.installed / "package.json"
        original.rename(self.root / "saved-package.json")
        original.symlink_to(outside)
        with self.assertRaises(AcceptanceFailure): self.verify()

    def test_running_registration_must_resolve_to_current_installation(self):
        other = self.root / "isolated/other"
        shutil.copytree(self.source, other)
        self.registration["plugins"][0]["rootDir"] = str(other)
        with self.assertRaises(AcceptanceFailure): self.verify()

    def test_missing_duplicate_or_unhealthy_registration_is_rejected(self):
        row = self.registration["plugins"][0]
        for rows in ([], [row, row], [{**row, "status": "failed"}], [{**row, "enabled": False}]):
            with self.subTest(rows=rows):
                self.registration["plugins"] = rows
                with self.assertRaises(AcceptanceFailure): self.verify()


if __name__ == "__main__": unittest.main()
