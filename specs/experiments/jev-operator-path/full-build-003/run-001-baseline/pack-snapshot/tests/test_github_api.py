from __future__ import annotations

import io
import json
import pathlib
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "assets" / "scripts"))

import github_api


def subprocess_result(stdout: str, stderr: str = "", returncode: int = 0):
    return type("Result", (), {"stdout": stdout, "stderr": stderr, "returncode": returncode})()


class GitHubAPITests(unittest.TestCase):
    def test_parse_github_url_accepts_only_full_issue_or_pr_urls(self) -> None:
        issue = github_api.parse_github_url("https://github.com/owner/repo/issues/123", expected_kind="issue")
        pr = github_api.parse_github_url("https://github.com/owner/repo/pull/456", expected_kind="pull")

        self.assertEqual(issue.repo_slug, "owner/repo")
        self.assertEqual(issue.kind, "issue")
        self.assertEqual(issue.number, 123)
        self.assertEqual(issue.canonical_url, "https://github.com/owner/repo/issues/123")
        self.assertEqual(pr.kind, "pull")
        self.assertEqual(pr.number, 456)

        bad_values = [
            "owner/repo#123",
            "#123",
            "123",
            "github.com/owner/repo/issues/123",
            "http://github.com/owner/repo/issues/123",
            "https://example.com/owner/repo/issues/123",
            "https://github.com/owner/repo/issues/not-a-number",
            "https://github.com/owner/repo/issues/123/comments/1",
        ]
        for value in bad_values:
            with self.subTest(value=value), self.assertRaises(github_api.GitHubAPIError):
                github_api.parse_github_url(value)

    def test_issue_snapshot_normalizes_body_hash_and_labels(self) -> None:
        payload = {
            "title": "Bug report",
            "body": "steps to reproduce",
            "state": "open",
            "user": {"login": "reporter"},
            "labels": [{"name": "bug"}, {"name": "triage"}],
            "html_url": "https://github.com/owner/repo/issues/123",
            "url": "https://api.github.com/repos/owner/repo/issues/123",
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-02T00:00:00Z",
        }

        with mock.patch("github_api.subprocess.run", return_value=subprocess_result(json.dumps(payload))) as run:
            snapshot = github_api.issue_snapshot("https://github.com/owner/repo/issues/123")

        self.assertEqual(run.call_args.args[0], ["gh", "api", "repos/owner/repo/issues/123"])
        self.assertEqual(snapshot["repo"], "owner/repo")
        self.assertEqual(snapshot["body_hash"], "sha256:a5cdbfe55af8c3143f8dabf722bbfecb699122cb0c986db748f5afd09e684fda")
        self.assertEqual(snapshot["labels"], ["bug", "triage"])

    def test_pr_snapshot_normalizes_head_sha_and_refs(self) -> None:
        payload = {
            "title": "Fix bug",
            "body": "PR body",
            "state": "open",
            "user": {"login": "contributor"},
            "head": {"sha": "abc123", "ref": "fix/bug", "repo": {"full_name": "fork/repo"}},
            "base": {"ref": "main", "repo": {"full_name": "owner/repo"}},
            "html_url": "https://github.com/owner/repo/pull/9",
            "url": "https://api.github.com/repos/owner/repo/pulls/9",
            "created_at": "2026-05-01T00:00:00Z",
            "updated_at": "2026-05-02T00:00:00Z",
        }

        with mock.patch("github_api.subprocess.run", return_value=subprocess_result(json.dumps(payload))) as run:
            snapshot = github_api.pr_snapshot("https://github.com/owner/repo/pull/9")

        self.assertEqual(run.call_args.args[0], ["gh", "api", "repos/owner/repo/pulls/9"])
        self.assertEqual(snapshot["repo"], "owner/repo")
        self.assertEqual(snapshot["head_sha"], "abc123")
        self.assertEqual(snapshot["head_ref"], "fix/bug")
        self.assertEqual(snapshot["base_ref"], "main")
        self.assertEqual(snapshot["author"], "contributor")

    def test_actor_returns_authenticated_login(self) -> None:
        with mock.patch("github_api.subprocess.run", return_value=subprocess_result('{"login":"octocat"}')):
            self.assertEqual(github_api.actor()["login"], "octocat")

    def test_create_and_update_comment_use_issue_comment_endpoint(self) -> None:
        comment = {
            "id": 111,
            "html_url": "https://github.com/owner/repo/issues/123#issuecomment-111",
            "url": "https://api.github.com/repos/owner/repo/issues/comments/111",
            "user": {"login": "bot"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            body_path = pathlib.Path(tmp) / "comment.md"
            body_path.write_text("hello\n", encoding="utf-8")
            with mock.patch("github_api.subprocess.run", return_value=subprocess_result(json.dumps(comment))) as run:
                created = github_api.comment_create("https://github.com/owner/repo/pull/123", body_path)

            self.assertEqual(
                run.call_args.args[0],
                ["gh", "api", "-X", "POST", "repos/owner/repo/issues/123/comments", "-f", "body=hello\n"],
            )
            self.assertEqual(created["id"], 111)

            with mock.patch("github_api.subprocess.run", return_value=subprocess_result(json.dumps(comment))) as run:
                updated = github_api.comment_update("owner/repo", 111, body_path)

            self.assertEqual(
                run.call_args.args[0],
                ["gh", "api", "-X", "PATCH", "repos/owner/repo/issues/comments/111", "-f", "body=hello\n"],
            )
            self.assertEqual(updated["author"], "bot")

    def test_pr_create_and_update_use_pull_request_endpoint(self) -> None:
        created_payload = {
            "number": 12,
            "html_url": "https://github.com/owner/repo/pull/12",
            "url": "https://api.github.com/repos/owner/repo/pulls/12",
            "state": "open",
            "draft": True,
            "user": {"login": "bot"},
        }
        with tempfile.TemporaryDirectory() as tmp:
            title_path = pathlib.Path(tmp) / "title.txt"
            body_path = pathlib.Path(tmp) / "body.md"
            title_path.write_text("Fix issue\n", encoding="utf-8")
            body_path.write_text("Details\n", encoding="utf-8")
            with mock.patch("github_api.subprocess.run", return_value=subprocess_result(json.dumps(created_payload))) as run:
                created = github_api.pr_create(
                    "owner/repo",
                    head="fix/issue",
                    base="main",
                    title_path=title_path,
                    body_path=body_path,
                    draft=True,
                )

            self.assertEqual(
                run.call_args.args[0],
                [
                    "gh",
                    "api",
                    "-X",
                    "POST",
                    "repos/owner/repo/pulls",
                    "-f",
                    "head=fix/issue",
                    "-f",
                    "base=main",
                    "-f",
                    "title=Fix issue",
                    "-f",
                    "body=Details\n",
                    "-F",
                    "draft=true",
                ],
            )
            self.assertEqual(created["number"], 12)

            with mock.patch("github_api.subprocess.run", return_value=subprocess_result(json.dumps(created_payload))) as run:
                updated = github_api.pr_update("https://github.com/owner/repo/pull/12", title_path, body_path)

            self.assertEqual(
                run.call_args.args[0],
                [
                    "gh",
                    "api",
                    "-X",
                    "PATCH",
                    "repos/owner/repo/pulls/12",
                    "-f",
                    "title=Fix issue",
                    "-f",
                    "body=Details\n",
                ],
            )
            self.assertEqual(updated["url"], "https://github.com/owner/repo/pull/12")

    def test_gh_api_surfaces_nonzero_exit_stderr(self) -> None:
        with mock.patch("github_api.subprocess.run", return_value=subprocess_result("", stderr="missing auth", returncode=1)):
            with self.assertRaisesRegex(github_api.GitHubAPIError, "missing auth"):
                github_api.gh_api(["user"])

    def test_gh_api_rejects_malformed_and_non_container_json(self) -> None:
        with mock.patch("github_api.subprocess.run", return_value=subprocess_result("not-json")):
            with self.assertRaisesRegex(github_api.GitHubAPIError, "invalid JSON"):
                github_api.gh_api(["user"])

        with mock.patch("github_api.subprocess.run", return_value=subprocess_result('"scalar"')):
            with self.assertRaisesRegex(github_api.GitHubAPIError, "not an object or list"):
                github_api.gh_api(["user"])

    def test_pr_search_encodes_marker_quotes(self) -> None:
        with mock.patch("github_api.subprocess.run", return_value=subprocess_result('{"items":[]}')) as run:
            result = github_api.pr_search("owner/repo", 'gc:review" is:closed', author="octocat")

        self.assertEqual(result["items"], [])
        request = run.call_args.args[0][-1]
        self.assertNotIn('"', request)
        self.assertIn("%22gc:review%22 is:closed%22", request)

    def test_main_prints_error_line_on_invalid_input(self) -> None:
        stderr = io.StringIO()

        with redirect_stderr(stderr), redirect_stdout(io.StringIO()):
            code = github_api.main(["parse-url", "owner/repo#123"])

        self.assertEqual(code, 1)
        self.assertIn("error:", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
