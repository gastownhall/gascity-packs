import pathlib
import sys
import unittest
import io
from unittest import mock


sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import github_intake_comment_issue as comment_issue


class GitHubIntakeCommentIssueTests(unittest.TestCase):
    def test_main_uses_profile_identity_when_provided(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            [
                "github_intake_comment_issue.py",
                "owner/repo",
                "42",
                "--installation-id",
                "profile-installation",
                "--github-app-identity",
                "mayor",
                "--body",
                "ack",
            ],
        ), mock.patch.object(
            comment_issue,
            "load_profile_github_app",
            return_value={"app_id": "mayor-app", "private_key_pem": "pem"},
        ) as load_profile_github_app, mock.patch.object(
            comment_issue.common,
            "post_issue_comment",
            return_value={"id": "100", "html_url": "https://github.com/owner/repo/issues/42#issuecomment-100"},
        ) as post_issue_comment, mock.patch.object(sys, "stdout", io.StringIO()):
            self.assertEqual(comment_issue.main(), 0)

        load_profile_github_app.assert_called_once_with("mayor")
        post_issue_comment.assert_called_once()
        self.assertEqual(post_issue_comment.call_args.args[0]["app_id"], "mayor-app")
        self.assertEqual(post_issue_comment.call_args.args[1:5], ("profile-installation", "owner", "repo", "42"))
        self.assertEqual(post_issue_comment.call_args.args[5], "ack")

    def test_main_uses_effective_config_by_default(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            [
                "github_intake_comment_issue.py",
                "owner/repo",
                "42",
                "--installation-id",
                "repo-installation",
                "--body",
                "ack",
            ],
        ), mock.patch.object(
            comment_issue.common,
            "load_effective_config",
            return_value={"app": {"app_id": "repo-app", "private_key_pem": "pem"}},
        ) as load_effective_config, mock.patch.object(
            comment_issue.common,
            "post_issue_comment",
            return_value={"id": "100"},
        ) as post_issue_comment, mock.patch.object(sys, "stdout", io.StringIO()):
            self.assertEqual(comment_issue.main(), 0)

        load_effective_config.assert_called_once()
        self.assertEqual(post_issue_comment.call_args.args[0]["app_id"], "repo-app")
        self.assertEqual(post_issue_comment.call_args.args[1:5], ("repo-installation", "owner", "repo", "42"))

    def test_main_uses_identity_installation_id_when_flag_omitted(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            [
                "github_intake_comment_issue.py",
                "owner/repo",
                "42",
                "--github-app-identity",
                "mayor",
                "--body",
                "ack",
            ],
        ), mock.patch.object(
            comment_issue,
            "load_profile_github_app",
            return_value={"app_id": "mayor-app", "private_key_pem": "pem", "installation_id": "profile-installation"},
        ), mock.patch.object(
            comment_issue.common,
            "post_issue_comment",
            return_value={"id": "100"},
        ) as post_issue_comment, mock.patch.object(sys, "stdout", io.StringIO()):
            self.assertEqual(comment_issue.main(), 0)

        self.assertEqual(post_issue_comment.call_args.args[1], "profile-installation")

    def test_main_rejects_invalid_identity(self) -> None:
        with mock.patch.object(
            sys,
            "argv",
            [
                "github_intake_comment_issue.py",
                "owner/repo",
                "42",
                "--github-app-identity",
                "secret/store/path",
                "--body",
                "ack",
            ],
        ):
            with self.assertRaisesRegex(SystemExit, "github_app_identity"):
                comment_issue.main()


if __name__ == "__main__":
    unittest.main()
