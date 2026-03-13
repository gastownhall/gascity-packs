from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from rlm_common import RuntimeConfig, ensure_runtime_layout, load_runtime_config, save_runtime_config, stage_corpus


class RuntimeConfigTests(unittest.TestCase):
    def test_runtime_config_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            city_root = Path(tmp)
            ensure_runtime_layout(city_root)
            cfg = RuntimeConfig(
                backend="openai",
                model="test-model",
                base_url="http://127.0.0.1:8000/v1",
                backend_api_key_env="",
                remote_backend_allowed=False,
                allowed_environments=["local"],
                default_environment="local",
                docker_image="",
                installed_at="2026-03-13T00:00:00+00:00",
            )
            save_runtime_config(city_root, cfg)
            loaded = load_runtime_config(city_root)
            self.assertEqual(loaded.model, "test-model")
            self.assertEqual(loaded.base_url, "http://127.0.0.1:8000/v1")
            self.assertEqual(loaded.allowed_environments, ["local"])
            self.assertEqual(loaded.default_environment, "local")


class StageCorpusTests(unittest.TestCase):
    def test_stage_corpus_skips_gitignored_secrets_and_binary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            city_root = Path(tmp)
            ensure_runtime_layout(city_root)

            (city_root / "keep.txt").write_text("hello\nworld\n", encoding="utf-8")
            (city_root / ".env").write_text("SECRET=value\n", encoding="utf-8")
            (city_root / "ignored.log").write_text("ignore me\n", encoding="utf-8")
            (city_root / "binary.bin").write_bytes(b"\x00\xff\x00\xff")

            subprocess.run(["git", "init"], cwd=city_root, check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@example.com"],
                cwd=city_root,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "config", "user.name", "Test User"],
                cwd=city_root,
                check=True,
                capture_output=True,
            )
            (city_root / ".gitignore").write_text("ignored.log\n", encoding="utf-8")

            bundle = stage_corpus(
                city_root=city_root,
                cwd=city_root,
                path_args=["."],
                glob_args=[],
                stdin_text=None,
                cfg=RuntimeConfig(default_environment="local", allowed_environments=["local"]),
            )

            staged_paths = {entry.display_path for entry in bundle.files}
            self.assertIn("keep.txt", staged_paths)
            self.assertIn(".gitignore", staged_paths)
            self.assertNotIn(".env", staged_paths)
            self.assertNotIn("ignored.log", staged_paths)
            self.assertNotIn("binary.bin", staged_paths)
            self.assertIn(".env", bundle.truncated_paths)
            self.assertIn(str((city_root / "ignored.log").as_posix()), bundle.truncated_paths)


if __name__ == "__main__":
    unittest.main()
