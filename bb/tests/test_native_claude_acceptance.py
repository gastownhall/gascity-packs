import json
import hashlib
import os
from pathlib import Path
import tempfile
import subprocess
import unittest

from native_claude_acceptance import prepare_native_claude


class NativeClaudeAcceptanceTest(unittest.TestCase):
    def test_isolates_generated_state_and_preserves_identity_reference(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source = base / "source.json"
            binary = base / "claude"
            binary.write_text('#!/bin/sh\nprintf "%s\\n" "$CLAUDE_CODE_DISABLE_AUTO_MEMORY" "$1"\n')
            binary.chmod(0o700)
            original = {"home_root": "/existing/homes", "session_root": "/existing/history",
                        "identity_file": "/private/current.jwt", "pool_id": "native-claude",
                        "claude_binary": str(binary), "claude_sha256": hashlib.sha256(binary.read_bytes()).hexdigest()}
            source.write_text(json.dumps(original))
            root = base / "scratch"
            root.mkdir()
            root = root.resolve()
            target = prepare_native_claude(root, source)
            actual = json.loads(target.read_text())
            self.assertEqual(json.loads(source.read_text()), original)
            self.assertEqual(actual["identity_file"], original["identity_file"])
            self.assertEqual(actual["home_root"], str(root / "native-claude-homes"))
            self.assertEqual(actual["session_root"], str(root / "claude-config/projects"))
            self.assertEqual(target.stat().st_mode & 0o777, 0o600)
            wrapper = Path(actual["claude_binary"])
            self.assertTrue(wrapper.is_relative_to(root))
            self.assertEqual(hashlib.sha256(wrapper.read_bytes()).hexdigest(), actual["claude_sha256"])
            result = subprocess.run([str(wrapper), "literal argument"], env={"PATH": os.environ["PATH"]},
                                    capture_output=True, text=True, check=True)
            self.assertEqual(result.stdout, "1\nliteral argument\n")
            provenance = json.loads(target.with_suffix(".provenance.json").read_text())
            self.assertEqual(provenance["originalExecutable"], {"path": str(binary), "sha256": original["claude_sha256"]})
            fixture = root / "fixture"
            fixture.mkdir()
            nested = prepare_native_claude(fixture, target)
            nested_provenance = json.loads(nested.with_suffix(".provenance.json").read_text())
            self.assertEqual(nested_provenance["originalExecutable"], provenance["originalExecutable"])
            self.assertEqual(json.loads(target.read_text()), actual)
            with self.assertRaises(FileExistsError):
                prepare_native_claude(root, source)
            binary.write_text("#!/bin/sh\necho altered-binary-ran\n")
            refused = subprocess.run([str(wrapper)], capture_output=True, text=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertNotIn("altered-binary-ran", refused.stdout)


if __name__ == "__main__":
    unittest.main()
