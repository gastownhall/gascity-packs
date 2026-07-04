from __future__ import annotations

import os
import pathlib
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timezone

import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import github_intake_addressed as addressed


class GitHubIntakeAddressedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self._old_environ = os.environ.copy()
        os.environ["GC_CITY_ROOT"] = self.tempdir.name

    def tearDown(self) -> None:
        os.environ.clear()
        os.environ.update(self._old_environ)

    def test_sweep_comments_default_limit_scans_all(self) -> None:
        parser = addressed.build_parser()

        args = parser.parse_args(["sweep-comments"])

        self.assertEqual(args.limit, 0)

    def test_decode_json_stream_accepts_concatenated_paginated_json(self) -> None:
        values = addressed.decode_json_stream('{"items":[{"number":1}]}\n{"items":[{"number":2}]}')

        self.assertEqual(values[0]["items"][0]["number"], 1)
        self.assertEqual(values[1]["items"][0]["number"], 2)

    def test_gh_recent_items_uses_paginate_without_slurp(self) -> None:
        completed = mock.Mock(
            returncode=0,
            stdout='{"items":[{"number":42,"html_url":"https://github.com/owner/repo/issues/42","updated_at":"2026-05-28T00:00:00Z","title":"Bug"}]}',
            stderr="",
        )

        with mock.patch.object(addressed.subprocess, "run", return_value=completed) as run:
            items = addressed.gh_recent_items("owner/repo", datetime(2026, 5, 21, tzinfo=timezone.utc), 10, {"GH_TOKEN": "token"})

        command = run.call_args.args[0]
        self.assertNotIn("--slurp", command)
        self.assertEqual(command[:6], ["gh", "api", "--paginate", "-X", "GET", "search/issues"])
        query = next(arg.removeprefix("q=") for arg in command if arg.startswith("q="))
        self.assertIn("repo:owner/repo", query)
        self.assertIn("updated:>=2026-05-21", query)
        self.assertNotIn("is:open", query)
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertEqual(items[0]["number"], 42)

    def test_load_json_pages_command_reports_timeout(self) -> None:
        with mock.patch.object(
            addressed.subprocess,
            "run",
            side_effect=addressed.subprocess.TimeoutExpired(["gh", "api", "endpoint"], 30),
        ):
            with self.assertRaisesRegex(addressed.AddressedError, "timed out after 30s"):
                addressed.load_json_pages_command(["gh", "api", "endpoint"])

    def test_gh_env_for_repo_sets_enterprise_host_token(self) -> None:
        old_api_base = addressed.common.GITHUB_API_BASE
        addressed.common.GITHUB_API_BASE = "https://github.enterprise.example/api/v3"
        self.addCleanup(setattr, addressed.common, "GITHUB_API_BASE", old_api_base)

        with mock.patch.object(addressed.common, "create_installation_token", return_value="token-123"):
            env = addressed.gh_env_for_repo(
                {"full_name": "owner/repo", "installation_id": "88"},
                {"app_id": "1", "private_key_pem": "pem"},
            )

        self.assertEqual(env["GH_TOKEN"], "token-123")
        self.assertEqual(env["GH_HOST"], "github.enterprise.example")
        self.assertEqual(env["GH_ENTERPRISE_TOKEN"], "token-123")

    def test_sweep_comments_skips_repos_without_installation_id(self) -> None:
        rules = {
            "repos": [
                {
                    "full_name": "owner/repo",
                    "addresses": [{"address": "@mayor", "pool": "mayor", "formula": "github-addressed-message"}],
                }
            ]
        }

        with mock.patch.object(addressed.common, "load_rules", return_value=rules), mock.patch.object(
            addressed.common,
            "load_effective_config",
            return_value={"app": {}},
        ), mock.patch.object(addressed, "gh_env_for_repo") as gh_env_for_repo:
            result = addressed.sweep_comments(limit=0, days=7)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["processed_count"], 0)
        self.assertEqual(result["failure_count"], 0)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(result["skipped"][0]["reason"], "installation_missing")
        gh_env_for_repo.assert_not_called()

    def test_order_script_runs_sweep_and_router(self) -> None:
        pack_root = pathlib.Path(__file__).resolve().parents[1]
        script = pack_root / "orders" / "scripts" / "github-addressed-message-router.sh"

        contents = script.read_text(encoding="utf-8")

        self.assertEqual(contents.count("github_intake_addressed.py"), 2)
        self.assertIn("github_intake_addressed.py\" sweep-comments", contents)
        self.assertIn("--limit \"$sweep_limit\" --days \"$sweep_days\"", contents)
        self.assertIn("github_intake_addressed.py\" router-scan --fail-on-error", contents)

    def test_addressed_formula_quotes_acknowledgement_heredoc(self) -> None:
        pack_root = pathlib.Path(__file__).resolve().parents[1]
        formula = pack_root / "formulas" / "github-addressed-message.formula.toml"

        contents = formula.read_text(encoding="utf-8")

        self.assertIn("cat >\"$BODY\" <<'EOF'", contents)
        self.assertIn('export GC_CITY_ROOT="{{city_root}}"', contents)


if __name__ == "__main__":
    unittest.main()
