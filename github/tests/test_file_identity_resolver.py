from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "examples"))

import file_identity_resolver as resolver


class FileIdentityResolverTests(unittest.TestCase):
    def test_load_identity_reads_schema_v1_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            identity_dir = pathlib.Path(tmpdir)
            (identity_dir / "mayor.json").write_text(
                json.dumps(
                    {
                        "schema_version": resolver.SCHEMA_VERSION,
                        "app_id": "123",
                        "installation_id": "456",
                        "private_key_pem": "pem",
                        "ready": True,
                    }
                ),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"GITHUB_INTAKE_IDENTITY_DIR": tmpdir}, clear=True):
                payload = resolver.load_identity("mayor")

        self.assertEqual(payload["app_id"], "123")
        self.assertEqual(payload["schema_version"], resolver.SCHEMA_VERSION)

    def test_load_identity_rejects_path_like_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "identity must match"):
            resolver.load_identity("../mayor")

    def test_load_identity_rejects_missing_schema_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            (pathlib.Path(tmpdir) / "mayor.json").write_text(
                json.dumps({"app_id": "123", "private_key_pem": "pem"}),
                encoding="utf-8",
            )
            with mock.patch.dict(os.environ, {"GITHUB_INTAKE_IDENTITY_DIR": tmpdir}, clear=True):
                with self.assertRaisesRegex(ValueError, "schema_version"):
                    resolver.load_identity("mayor")


if __name__ == "__main__":
    unittest.main()
