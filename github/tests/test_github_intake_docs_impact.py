from __future__ import annotations

import pathlib
import sys
import unittest
import hashlib
import json
import tempfile
from unittest import mock

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

import github_intake_docs_impact as impact
import github_intake_docs_review_runtime as runtime


SHA = "a" * 40


def review() -> dict[str, object]:
    diff = """diff --git a/docs/guide.md b/docs/guide.md
index 1111111..2222222 100644
--- a/docs/guide.md
+++ b/docs/guide.md
@@ -1 +1 @@
-Old guidance.
+New guidance.
"""
    proposal = {
        "schema_version": 1, "status": "proposed", "generated_at": "2026-08-31T12:00:00Z",
        "identity": {"repository_id": "17", "repository": "allenday/demo", "pr_number": 9, "base_sha": "b" * 40, "head_sha": SHA, "head_repository_id": "17", "head_repository": "allenday/demo", "base_ref": "main"},
        "patch_sha256": hashlib.sha256(diff.encode()).hexdigest(), "diff": diff,
        "files": [{"path": "docs/guide.md", "sha256": "c" * 64}],
        "claims": [{"claim": "The guide documents the workflow.", "evidence": f"github://allenday/demo/blob/{SHA}/README.md", "release_scope": "unreleased"}],
        "checks": [{"command": "make docs-check", "status": "passed", "explanation": "Documentation checks passed."}],
    }
    return {"schema_version": 1, "kind": "github-pr-docs-impact-review", "identity": {"repository_id": "17", "repository": "allenday/demo", "pr_number": 9, "head_sha": SHA, "source_key": f"github-pr:17:9:{SHA}"}, "agent_skill": "developer-experience-techdocs", "verdict": "proposal-ready", "rationale": "A bounded documentation patch is ready.", "evidence": [{"path": "docs/guide.md", "evidence": f"github://allenday/demo/blob/{SHA}/docs/guide.md"}], "confidence": 0.9, "proposal": proposal}


def pull_request(*, head_repository: str = "allenday/demo", head_repository_id: str = "17", head_ref: str = "feature/docs", head_sha: str = SHA) -> dict[str, object]:
    return {
        "number": 9,
        "head": {"sha": head_sha, "ref": head_ref, "repo": {"id": head_repository_id, "full_name": head_repository}},
        "base": {"sha": "b" * 40, "ref": "main", "repo": {"id": "17", "full_name": "allenday/demo"}},
    }


class DocsImpactProjectionTests(unittest.TestCase):
    def test_valid_same_repository_review_gets_an_app_owned_stacked_plan(self) -> None:
        plan = impact.followup_pr_plan(pull_request(), review())

        self.assertEqual(plan, {
            "repository": "allenday/demo",
            "branch": "gas-city/docs-9-" + review()["proposal"]["patch_sha256"][:12],
            "base": "feature/docs",
            "head_sha": SHA,
        })

    def test_fork_wrong_identity_or_stale_review_cannot_get_a_followup_plan(self) -> None:
        wrong_identity = review()
        wrong_identity["proposal"]["identity"]["base_ref"] = "release"
        for current, candidate in (
            (pull_request(head_repository="fork/demo", head_repository_id="99"), review()),
            (pull_request(), wrong_identity),
            (pull_request(head_sha="c" * 40), review()),
        ):
            with self.subTest(current=current):
                self.assertIsNone(impact.followup_pr_plan(current, candidate))

    def test_compact_check_never_contains_a_diff_or_internal_dashboard_link(self) -> None:
        output = impact.compact_check_output(review(), {"url": "https://github.com/allenday/demo/pull/10", "number": "10"})

        self.assertEqual(output["title"], "Documentation impact: follow-up ready")
        self.assertIn("#10", output["summary"])
        self.assertNotIn("diff --git", output["summary"])
        self.assertNotIn("dashboard", output["summary"].lower())
        self.assertNotIn("gas-city", output["summary"].lower())

    def test_followup_gateway_finds_a_marker_on_a_later_page(self) -> None:
        gateway = impact.GitHubAppProjectionGateway({"slug": "gas-city"}, "1")
        pages = [
            [{"number": 1, "html_url": "https://github.com/allenday/demo/pull/1", "body": "other"}],
            [{"number": 10, "html_url": "https://github.com/allenday/demo/pull/10", "body": "<!-- marker -->", "head": {"ref": "gas-city/docs-9-deadbeef", "repo": {"full_name": "allenday/demo"}, "user": {"login": "gas-city[bot]"}}, "base": {"repo": {"full_name": "allenday/demo"}}}],
        ]
        with mock.patch.object(impact.common, "create_installation_token", return_value="token"), mock.patch.object(impact.common, "github_api_paginated_list_request", return_value=[item for page in pages for item in page]) as listed:
            found = gateway.find_followup("allenday/demo", "gas-city/docs-9-deadbeef", "marker")

        self.assertEqual(found, {"number": "10", "url": "https://github.com/allenday/demo/pull/10"})
        self.assertTrue(listed.called)

    def test_forged_contributor_marker_and_prefix_is_never_adopted_or_closed(self) -> None:
        gateway = impact.GitHubAppProjectionGateway({"slug": "gas-city"}, "1")
        forged = {
            "number": 10, "html_url": "https://github.com/allenday/demo/pull/10", "body": "<!-- marker -->",
            "head": {"ref": "gas-city/docs-9-deadbeef", "repo": {"full_name": "allenday/demo"}, "user": {"login": "contributor"}},
            "base": {"repo": {"full_name": "allenday/demo"}},
        }
        with mock.patch.object(impact.common, "create_installation_token", return_value="token"), mock.patch.object(impact.common, "github_api_paginated_list_request", return_value=[forged]):
            self.assertIsNone(gateway.find_followup("allenday/demo", "gas-city/docs-9-deadbeef", "marker"))
        with mock.patch.object(impact.common, "create_installation_token", return_value="token"), mock.patch.object(impact.common, "github_api_request", return_value=forged) as requested:
            with self.assertRaisesRegex(impact.common.GitHubAPIError, "owned"):
                gateway.close_followup("allenday/demo", "10", "gas-city/docs-9-deadbeef", "marker")

        self.assertEqual(requested.call_count, 1)

    def test_bot_followup_with_wrong_branch_or_marker_substring_is_never_owned(self) -> None:
        gateway = impact.GitHubAppProjectionGateway({"slug": "gas-city"}, "1")
        expected_branch = "gas-city/docs-9-deadbeef"
        def pull(*, branch: str, body: str) -> dict[str, object]:
            return {
                "number": 10, "html_url": "https://github.com/allenday/demo/pull/10", "body": body,
                "head": {"ref": branch, "repo": {"full_name": "allenday/demo"}, "user": {"login": "gas-city[bot]"}},
                "base": {"repo": {"full_name": "allenday/demo"}},
            }
        wrong_branch = pull(branch="gas-city/docs-9-other", body="<!-- marker -->")
        substring = pull(branch=expected_branch, body="<!-- marker-extra -->")
        with mock.patch.object(impact.common, "create_installation_token", return_value="token"), mock.patch.object(impact.common, "github_api_paginated_list_request", side_effect=[[wrong_branch], [substring]]):
            self.assertIsNone(gateway.find_followup("allenday/demo", expected_branch, "marker"))
            self.assertIsNone(gateway.find_followup("allenday/demo", expected_branch, "marker"))
        with mock.patch.object(impact.common, "create_installation_token", return_value="token"), mock.patch.object(impact.common, "github_api_request", return_value=wrong_branch) as requested:
            with self.assertRaisesRegex(impact.common.GitHubAPIError, "owned"):
                gateway.close_followup("allenday/demo", "10", expected_branch, "marker")
        self.assertEqual(requested.call_count, 1)

    def test_wrong_repo_duplicate_or_substring_marker_never_authorizes_adoption_or_close(self) -> None:
        gateway = impact.GitHubAppProjectionGateway({"slug": "gas-city"}, "1")
        branch, marker = "gas-city/docs-9-deadbeef", "marker"
        def pull(*, repository: str = "allenday/demo", body: str = "<!-- marker -->") -> dict[str, object]:
            return {"number": 10, "html_url": "https://github.com/allenday/demo/pull/10", "body": body, "head": {"ref": branch, "repo": {"full_name": repository}, "user": {"login": "gas-city[bot]"}}, "base": {"repo": {"full_name": "allenday/demo"}}}
        cases = (pull(repository="fork/demo"), pull(body="<!-- marker -->\n<!-- marker -->"), pull(body="<!-- marker-extra -->"))
        with mock.patch.object(impact.common, "create_installation_token", return_value="token"), mock.patch.object(impact.common, "github_api_paginated_list_request", side_effect=[[case] for case in cases]):
            for _ in cases:
                self.assertIsNone(gateway.find_followup("allenday/demo", branch, marker))
        with mock.patch.object(impact.common, "create_installation_token", return_value="token"), mock.patch.object(impact.common, "github_api_request", return_value=cases[-1]) as requested:
            with self.assertRaisesRegex(impact.common.GitHubAPIError, "owned"):
                gateway.close_followup("allenday/demo", "10", branch, marker)
        self.assertEqual(requested.call_count, 1)

    def test_paginated_discovery_reads_the_second_page_before_deciding(self) -> None:
        first = [{"number": number} for number in range(100)]
        second = [{"number": 10, "html_url": "https://github.com/allenday/demo/pull/10", "body": "<!-- marker -->"}]
        with mock.patch.object(impact.common, "github_api_list_request", side_effect=[first, second]) as listed:
            values = impact.common.github_api_paginated_list_request("GET", "/repos/allenday/demo/pulls?state=all", bearer_token="token")

        self.assertEqual(values[-1]["number"], 10)
        self.assertEqual(listed.call_count, 2)

    def test_later_page_check_is_updated_without_a_duplicate_post(self) -> None:
        gateway = impact.GitHubAppProjectionGateway({}, "1")
        run = {"external_id": "docs-impact:run", "assignment": {"identity": review()["identity"]}}
        output = {"title": "Documentation impact: action required", "summary": "Act."}
        with mock.patch.object(impact.common, "get_pull_request", return_value=pull_request()), mock.patch.object(impact.common, "find_check_run", return_value={"id": "99", "external_id": "docs-impact:run"}), mock.patch.object(impact.common, "update_check_run", return_value={"id": "99"}) as updated, mock.patch.object(impact.common, "create_check_run", side_effect=AssertionError("must not create a duplicate Check Run")):
            gateway.ensure_check(run, "action_required", output)

        updated.assert_called_once()

    def test_terminal_check_race_is_rendered_stale_without_creating_followup(self) -> None:
        class Gateway:
            def __init__(self) -> None: self.calls = 0; self.check = None
            def pull_request(self, run: dict[str, object]) -> dict[str, object]:
                self.calls += 1
                return pull_request() if self.calls == 1 else pull_request(head_sha="c" * 40)
            def find_followup(self, *args: object) -> dict[str, str]: return {"number": "10", "url": "https://github.com/allenday/demo/pull/10"}
            def branch_exists(self, *args: object) -> bool: raise AssertionError("must not create followup")
            def branch_matches(self, *args: object) -> bool: raise AssertionError("must not create followup")
            def create_branch(self, *args: object) -> str: raise AssertionError("must not create followup")
            def create_followup(self, *args: object) -> dict[str, str]: raise AssertionError("must not create followup")
            def ensure_check(self, run: dict[str, object], conclusion: str, output: dict[str, str]) -> None: self.check = (conclusion, output)

        with tempfile.TemporaryDirectory() as directory:
            gateway = Gateway()
            run = {"identity": "run", "external_id": "docs-impact:run", "conclusion": "action_required", "assignment": {"identity": review()["identity"]}, "candidate": {"artifact": review()}}
            impact.AppProjection(runtime.FileDocsReviewStore(directory), gateway).perform("ensure_terminal_check", run)

        self.assertEqual(gateway.check[0], "action_required")
        self.assertEqual(gateway.check[1]["title"], "Documentation impact: stale revision")

    def test_concrete_gateway_rechecks_head_before_followup_post(self) -> None:
        gateway = impact.GitHubAppProjectionGateway({}, "1")
        with mock.patch.object(impact.common, "get_pull_request", return_value=pull_request(head_sha="c" * 40)), mock.patch.object(impact.common, "create_pull_request", side_effect=AssertionError("must not POST a stale followup")):
            with self.assertRaisesRegex(impact.common.GitHubAPIError, "changed"):
                gateway.create_followup("allenday/demo", "gas-city/docs-9-deadbeef", "feature/docs", "marker", review())

    def test_source_race_after_terminal_check_closes_only_the_marker_followup(self) -> None:
        class Gateway:
            def __init__(self) -> None: self.head_reads = 0; self.closed: list[tuple[str, str, str]] = []; self.checks: list[dict[str, str]] = []
            def pull_request(self, run: dict[str, object]) -> dict[str, object]:
                self.head_reads += 1
                return pull_request() if self.head_reads < 3 else pull_request(head_sha="c" * 40)
            def find_followup(self, *args: object) -> dict[str, str]: return {"number": "10", "url": "https://github.com/allenday/demo/pull/10"}
            def branch_exists(self, *args: object) -> bool: raise AssertionError("existing PR must be reused")
            def branch_matches(self, *args: object) -> bool: raise AssertionError("existing PR must be reused")
            def create_branch(self, *args: object) -> str: raise AssertionError("existing PR must be reused")
            def create_followup(self, *args: object) -> dict[str, str]: raise AssertionError("existing PR must be reused")
            def close_followup(self, repository: str, number: str, branch: str, marker: str) -> None: self.closed.append((repository, number, marker))
            def ensure_check(self, run: dict[str, object], conclusion: str, output: dict[str, str]) -> None: self.checks.append(output)

        with tempfile.TemporaryDirectory() as directory:
            gateway = Gateway()
            run = {"identity": "run", "external_id": "docs-impact:run", "conclusion": "action_required", "assignment": {"identity": review()["identity"]}, "candidate": {"artifact": review()}}
            impact.AppProjection(runtime.FileDocsReviewStore(directory), gateway).perform("ensure_terminal_check", run)

        self.assertEqual(run["state"], "stale")
        self.assertEqual(run["conclusion"], "action_required")
        self.assertEqual([number for _, number, _ in gateway.closed], ["10"])
        self.assertEqual(gateway.checks[-1]["title"], "Documentation impact: stale revision")

    def test_source_race_after_pr_creation_closes_that_followup(self) -> None:
        class Gateway:
            def __init__(self) -> None: self.head_reads = 0; self.closed: list[str] = []
            def pull_request(self, run: dict[str, object]) -> dict[str, object]:
                self.head_reads += 1
                return pull_request() if self.head_reads < 3 else pull_request(head_sha="c" * 40)
            def find_followup(self, *args: object) -> None: return None
            def branch_exists(self, *args: object) -> bool: return True
            def branch_matches(self, *args: object) -> bool: return True
            def create_branch(self, *args: object) -> str: raise AssertionError("must reuse branch")
            def create_followup(self, *args: object) -> dict[str, str]: return {"number": "10", "url": "https://github.com/allenday/demo/pull/10"}
            def close_followup(self, repository: str, number: str, branch: str, marker: str) -> None: self.closed.append(number)
            def ensure_check(self, run: dict[str, object], conclusion: str, output: dict[str, str]) -> None: pass

        with tempfile.TemporaryDirectory() as directory:
            gateway = Gateway()
            run = {"identity": "run", "external_id": "docs-impact:run", "conclusion": "action_required", "assignment": {"identity": review()["identity"]}, "candidate": {"artifact": review()}, "followup": {"state": "branch-created", "commit_sha": "d" * 40}}
            impact.AppProjection(runtime.FileDocsReviewStore(directory), gateway).perform("ensure_terminal_check", run)

        self.assertEqual(run["state"], "stale")
        self.assertEqual(gateway.closed, ["10"])

    def test_followup_failure_completes_action_required_check_instead_of_escaping(self) -> None:
        class FailingGateway:
            def pull_request(self, run: dict[str, object]) -> dict[str, object]:
                return pull_request()
            def find_followup(self, *args: object) -> None: return None
            def branch_exists(self, *args: object) -> bool: return False
            def branch_matches(self, *args: object) -> bool: return False
            def create_branch(self, *args: object) -> str: raise RuntimeError("stale at push")
            def create_followup(self, *args: object) -> dict[str, str]: raise AssertionError("unreachable")
            def ensure_check(self, run: dict[str, object], conclusion: str, output: dict[str, str]) -> None:
                self.check = (conclusion, output)

        with tempfile.TemporaryDirectory() as directory:
            gateway = FailingGateway()
            adapter = impact.AppProjection(runtime.FileDocsReviewStore(directory), gateway)
            run = {"identity": "run", "external_id": "docs-impact:run", "conclusion": "action_required", "assignment": {"identity": review()["identity"]}, "candidate": {"artifact": review()}}

            adapter.perform("ensure_terminal_check", run)

        self.assertEqual(gateway.check[0], "action_required")
        self.assertEqual(gateway.check[1]["title"], "Documentation impact: action required")

    def test_pr_timeout_is_terminal_then_retry_reuses_the_created_followup(self) -> None:
        class Gateway:
            def __init__(self) -> None:
                self.created: list[dict[str, str]] = []
                self.create_calls = 0
                self.checks: list[str] = []
            def pull_request(self, run: dict[str, object]) -> dict[str, object]: return pull_request()
            def find_followup(self, repository: str, branch: str, marker: str) -> dict[str, str] | None:
                return next((item for item in self.created if item["marker"] == marker), None)
            def branch_exists(self, *args: object) -> bool: return True
            def branch_matches(self, *args: object) -> bool: return True
            def create_branch(self, *args: object) -> str: raise AssertionError("must reuse existing App branch")
            def create_followup(self, repository: str, branch: str, base: str, marker: str, review: dict[str, object]) -> dict[str, str]:
                self.create_calls += 1
                created = {"number": "10", "url": "https://github.com/allenday/demo/pull/10", "marker": marker}
                self.created.append(created)
                raise RuntimeError("request timed out after GitHub created the PR")
            def ensure_check(self, run: dict[str, object], conclusion: str, output: dict[str, str]) -> None: self.checks.append(conclusion)

        with tempfile.TemporaryDirectory() as directory:
            gateway = Gateway()
            adapter = impact.AppProjection(runtime.FileDocsReviewStore(directory), gateway)
            run = {"identity": "run", "external_id": "docs-impact:run", "conclusion": "action_required", "assignment": {"identity": review()["identity"]}, "candidate": {"artifact": review()}, "followup": {"state": "branch-created", "commit_sha": "d" * 40}}
            adapter.perform("ensure_terminal_check", run)
            adapter.perform("ensure_terminal_check", run)

        self.assertEqual(gateway.create_calls, 1)
        self.assertEqual(gateway.checks, ["action_required", "action_required"])

    def test_retry_adopts_a_branch_created_before_a_crash_and_opens_one_followup(self) -> None:
        class Gateway:
            def __init__(self) -> None:
                self.branch_created = False
                self.branches: list[str] = []
                self.crash_after_branch = True
                self.pull_requests: list[dict[str, str]] = []
                self.checks: list[dict[str, object]] = []

            def pull_request(self, run: dict[str, object]) -> dict[str, object]:
                return pull_request()

            def find_followup(self, repository: str, branch: str, marker: str) -> dict[str, str] | None:
                return next((item for item in self.pull_requests if item["marker"] == marker), None)

            def branch_exists(self, repository: str, branch: str) -> bool:
                return self.branch_created

            def branch_matches(self, repository: str, branch: str, marker: str, commit_sha: str = "") -> bool:
                return self.branch_created

            def create_branch(self, repository: str, branch: str, head_sha: str, review: dict[str, object], marker: str, before_push: object) -> str:
                self.branch_created = True
                self.branches.append(branch)
                before_push("d" * 40)
                if self.crash_after_branch:
                    self.crash_after_branch = False
                    raise RuntimeError("simulated crash after branch creation")
                return "d" * 40

            def create_followup(self, repository: str, branch: str, base: str, marker: str, review: dict[str, object]) -> dict[str, str]:
                created = {"number": "10", "url": "https://github.com/allenday/demo/pull/10", "marker": marker}
                self.pull_requests.append(created)
                return created

            def ensure_check(self, run: dict[str, object], conclusion: str, output: dict[str, str]) -> None:
                self.checks.append({"conclusion": conclusion, "output": output})

        with tempfile.TemporaryDirectory() as directory:
            store = runtime.FileDocsReviewStore(directory)
            gateway = Gateway()
            adapter = impact.AppProjection(store, gateway)
            assignment = {"schema_version": 1, "kind": "github-pr-docs-impact-assignment", "identity": review()["identity"], "agent_skill": "developer-experience-techdocs", "evidence_bundle": {"head_sha": SHA, "proposal_identity": review()["proposal"]["identity"], "files": [{"path": "docs/guide.md", "reference": f"github://allenday/demo/blob/{SHA}/docs/guide.md", "patch": "@@ -1 +1 @@\n-old\n+new\n"}]}}
            runtime.intake_delivery(store, assignment, adapter, now=100)
            envelope = {"schema_version": 1, "snapshot_sha256": hashlib.sha256(json.dumps(assignment, sort_keys=True, separators=(",", ":")).encode()).hexdigest(), "artifact": review()}

            accepted = runtime.accept_candidate(store, envelope, adapter, now=101)
            self.assertTrue(accepted["accepted"])
            persisted = store.load(str(review()["identity"]["source_key"]))
            self.assertEqual(persisted["followup"]["state"], "action-required")
            self.assertEqual(persisted["followup"]["commit_sha"], "d" * 40)

            runtime.reconcile_pending(store, adapter, now=102)
            runtime.reconcile_pending(store, adapter, now=103)

            self.assertEqual(len(gateway.pull_requests), 1)
            self.assertEqual(gateway.branches, ["gas-city/docs-9-" + review()["proposal"]["patch_sha256"][:12]])
            self.assertEqual(store.load(str(review()["identity"]["source_key"]))["followup"]["state"], "created")
            self.assertEqual(gateway.checks[-1]["conclusion"], "action_required")


if __name__ == "__main__":
    unittest.main()
