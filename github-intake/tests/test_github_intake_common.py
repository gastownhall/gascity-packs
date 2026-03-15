from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import tempfile
import unittest

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import github_intake_common as common


class GitHubIntakeCommonTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name
        os.environ["GC_SERVICE_STATE_ROOT"] = os.path.join(self.tempdir.name, ".gc", "services", "github-intake")
        os.environ["GC_PUBLISHED_SERVICES_DIR"] = os.path.join(self.tempdir.name, ".gc", "services", ".published")
        os.makedirs(os.environ["GC_PUBLISHED_SERVICES_DIR"], exist_ok=True)

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def _write_snapshot(self, name: str, url: str) -> None:
        path = pathlib.Path(os.environ["GC_PUBLISHED_SERVICES_DIR"]) / f"{name}.json"
        path.write_text(
            json.dumps(
                {
                    "service_name": name,
                    "published": bool(url),
                    "visibility": "public",
                    "current_url": url,
                    "url_version": 1,
                }
            ),
            encoding="utf-8",
        )

    def test_build_manifest_uses_published_service_urls(self) -> None:
        self._write_snapshot(common.ADMIN_SERVICE_NAME, "https://admin.example.com")
        self._write_snapshot(common.WEBHOOK_SERVICE_NAME, "https://hook.example.com")

        manifest = common.build_manifest()

        self.assertEqual(manifest["url"], "https://admin.example.com")
        self.assertEqual(
            manifest["hook_attributes"]["url"],
            "https://hook.example.com/v0/github/webhook",
        )
        self.assertEqual(
            manifest["redirect_url"],
            "https://admin.example.com/v0/github/app/manifest/callback",
        )
        self.assertIn("issue_comment", manifest["default_events"])

    def test_parse_gc_command_accepts_one_token_command(self) -> None:
        self.assertEqual(common.parse_gc_command("\n/gc review\n"), "review")
        self.assertEqual(common.parse_gc_command("/gc question"), "question")
        self.assertEqual(common.parse_gc_command("please review this\n/gc review"), "review")
        self.assertIsNone(common.parse_gc_command("/gc review now"))

    def test_verify_github_signature(self) -> None:
        payload = b'{"ok":true}'
        secret = "top-secret"
        digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        self.assertTrue(common.verify_github_signature(secret, payload, f"sha256={digest}"))
        self.assertFalse(common.verify_github_signature(secret, payload, "sha256=deadbeef"))

    def test_extract_issue_comment_request_requires_pr_comment_and_command(self) -> None:
        payload = {
            "action": "created",
            "installation": {"id": 77},
            "issue": {"number": 42, "pull_request": {"url": "https://api.github.com/repos/o/r/pulls/42"}},
            "comment": {
                "id": 99,
                "body": "/gc review\nplease do the thing",
                "html_url": "https://github.com/owner/repo/pull/42#issuecomment-99",
                "user": {"login": "alice"},
            },
            "repository": {
                "id": 123,
                "name": "repo",
                "full_name": "Owner/Repo",
                "owner": {"login": "Owner"},
            },
        }

        request = common.extract_issue_comment_request(payload)

        self.assertIsNotNone(request)
        self.assertEqual(request["request_id"], "gh-123-99-review")
        self.assertEqual(request["repository_full_name"], "owner/repo")
        self.assertEqual(request["installation_id"], "77")
        self.assertEqual(request["comment_author"], "alice")
        self.assertEqual(request["command"], "review")
        payload["issue"] = {"number": 42}
        self.assertIsNone(common.extract_issue_comment_request(payload))

    def test_set_repo_mapping_persists_commands(self) -> None:
        config = common.set_repo_mapping(
            common.load_config(),
            "Owner/Repo",
            "product/polecat",
            "mol-review",
            "mol-question",
        )

        mapping = common.resolve_repo_mapping(config, "owner/repo")
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["target"], "product/polecat")
        self.assertEqual(mapping["commands"]["review"]["formula"], "mol-review")
        self.assertEqual(mapping["commands"]["question"]["formula"], "mol-question")

    def test_safe_storage_id_sanitizes_delivery_header_values(self) -> None:
        self.assertEqual(common.safe_storage_id("abc-123", "delivery"), "abc-123")
        sanitized = common.safe_storage_id("../../etc/passwd", "delivery")
        self.assertTrue(sanitized.startswith("delivery-"))
        self.assertNotIn("/", sanitized)

    def test_app_identifier_requires_app_id(self) -> None:
        self.assertEqual(common.app_identifier({"app_id": "123456"}), "123456")
        with self.assertRaises(common.GitHubAPIError):
            common.app_identifier({"client_id": "Iv1.only-client-id"})


if __name__ == "__main__":
    unittest.main()
