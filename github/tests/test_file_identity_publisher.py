from __future__ import annotations

import io
import json
import os
import pathlib
import stat
import sys
import tempfile
import unittest
from unittest import mock


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "examples"))

import file_identity_publisher as publisher
import file_identity_resolver as resolver


class FileIdentityPublisherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GITHUB_INTAKE_IDENTITY_DIR"] = self.tempdir.name

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def test_writes_0600_file_with_schema_and_derived_ready(self) -> None:
        path = publisher.publish(
            "demo-city",
            {"app_id": "123", "private_key_pem": "-----BEGIN-----\nline2\n-----END-----\n", "webhook_secret": "s3cr3t"},
        )

        self.assertTrue(path.exists())
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["schema_version"], publisher.SCHEMA_VERSION)
        self.assertEqual(payload["ready"], "true")
        self.assertIn("line2", payload["private_key_pem"])

    def test_partial_republish_merges_and_cannot_fake_ready(self) -> None:
        publisher.publish("c", {"app_id": "1", "permissions": "metadata=read", "repos": "demo"})

        path = publisher.publish("c", {"installation_id": "999", "ready": "true"})

        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(payload["installation_id"], "999")
        self.assertEqual(payload["permissions"], "metadata=read")
        self.assertEqual(payload["repos"], "demo")
        self.assertEqual(payload["ready"], "false")

    def test_round_trips_through_the_shipped_resolver(self) -> None:
        publisher.publish(
            "round",
            {"app_id": "42", "private_key_pem": "PEM", "webhook_secret": "w", "slug": "round-app"},
        )

        loaded = resolver.load_identity("round")

        self.assertEqual(loaded["app_id"], "42")
        self.assertEqual(loaded["slug"], "round-app")

    def test_bad_identity_rejected(self) -> None:
        with self.assertRaises(ValueError):
            publisher.publish("../escape", {"app_id": "1"})

    def test_main_takes_identity_argument_and_reports_derived_ready(self) -> None:
        payload = json.dumps({"app_id": "5"})

        with mock.patch.object(sys, "stdin", io.StringIO(payload)):
            with mock.patch.object(sys, "stdout", io.StringIO()) as out:
                code = publisher.main(["argv-identity"])

        self.assertEqual(code, 0)
        result = json.loads(out.getvalue())
        self.assertTrue(result["published"])
        self.assertFalse(result["ready"])
        self.assertTrue(pathlib.Path(self.tempdir.name, "argv-identity.json").exists())

    def test_main_without_identity_fails_with_usage_error(self) -> None:
        os.environ.pop("GITHUB_INTAKE_APP_IDENTITY", None)

        with mock.patch.object(sys, "stdin", io.StringIO("{}")):
            with mock.patch.object(sys, "stderr", io.StringIO()):
                code = publisher.main([])

        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
