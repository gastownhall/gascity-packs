"""Safe GitHub-native projection for a validated docs-impact review.

This module deliberately owns no reviewer work.  It turns the first accepted,
revision-bound candidate into a compact Check Run and (only where GitHub still
proves the source branch belongs to the base repository) an App-owned stacked
documentation follow-up.
"""

from __future__ import annotations

import copy
import base64
import os
import pathlib
import subprocess
import tempfile
from typing import Any, Callable, Protocol

import github_intake_common as common
import github_intake_docs_patch as docs_patch


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _pull_identity(pull_request: dict[str, Any]) -> dict[str, Any] | None:
    """Extract exactly the mutable GitHub facts that authorize a follow-up."""
    try:
        head, base = pull_request["head"], pull_request["base"]
        head_repo, base_repo = head["repo"], base["repo"]
        number = pull_request["number"]
        if type(number) is not int or number <= 0:
            return None
        result = {
            "repository_id": str(base_repo["id"]),
            "repository": _text(base_repo["full_name"]),
            "pr_number": number,
            "base_sha": _text(base["sha"]).lower(),
            "head_sha": _text(head["sha"]).lower(),
            "head_repository_id": str(head_repo["id"]),
            "head_repository": _text(head_repo["full_name"]),
            "base_ref": _text(base["ref"]),
            "head_ref": _text(head["ref"]),
        }
    except (KeyError, TypeError):
        return None
    return result if all(result.values()) else None


def followup_pr_plan(pull_request: dict[str, Any], review: dict[str, Any]) -> dict[str, str] | None:
    """Return the only branch/PR mutation an accepted review can authorize."""
    try:
        validated = docs_patch.validate_agent_review(review)
    except (TypeError, ValueError):
        return None
    current = _pull_identity(pull_request) if isinstance(pull_request, dict) else None
    proposal = validated.get("proposal")
    if current is None or validated["verdict"] != "proposal-ready" or not isinstance(proposal, dict):
        return None
    proposal_identity = proposal["identity"]
    if any(proposal_identity[key] != current[key] for key in proposal_identity):
        return None
    if current["head_repository_id"] != current["repository_id"] or current["head_repository"] != current["repository"]:
        return None
    digest = _text(proposal.get("patch_sha256"))
    if len(digest) != 64:
        return None
    return {
        "repository": current["repository"],
        "branch": f"gas-city/docs-{current['pr_number']}-{digest[:12]}",
        "base": current["head_ref"],
        "head_sha": current["head_sha"],
    }


def compact_check_output(review: dict[str, Any], followup: dict[str, Any] | None = None) -> dict[str, str]:
    """Render the original PR's entire user-facing result without a diff/UI."""
    verdict = _text(review.get("verdict")) if isinstance(review, dict) else ""
    if verdict == "proposal-ready":
        url = _text((followup or {}).get("url"))
        number = _text((followup or {}).get("number"))
        if url.startswith("https://") and number.isdigit():
            return {
                "title": "Documentation impact: follow-up ready",
                "summary": f"A documentation follow-up is ready: [PR #{number}]({url}). Review that PR, then merge it into this PR branch.",
            }
        return {
            "title": "Documentation impact: action required",
            "summary": "A documentation proposal was validated, but a safe App-owned follow-up PR could not be confirmed. Create or update the documentation on this pull request branch.",
        }
    if verdict in {"no-impact", "docs-sufficient"}:
        return {"title": "Documentation impact: complete", "summary": "Documentation review completed; no follow-up is required."}
    return {"title": "Documentation impact: action required", "summary": "Documentation review needs author action on this pull request."}


class ProjectionGateway(Protocol):
    """The sole seam for GitHub/App effects; implementations must never merge."""

    def pull_request(self, run: dict[str, Any]) -> dict[str, Any]: ...
    def find_followup(self, repository: str, branch: str, marker: str) -> dict[str, str] | None: ...
    def branch_exists(self, repository: str, branch: str) -> bool: ...
    def branch_matches(self, repository: str, branch: str, marker: str, commit_sha: str = "") -> bool: ...
    def create_branch(self, repository: str, branch: str, head_sha: str, review: dict[str, Any], marker: str, before_push: Callable[[str], None]) -> str: ...
    def create_followup(self, repository: str, branch: str, base: str, marker: str, review: dict[str, Any]) -> dict[str, str]: ...
    def close_followup(self, repository: str, number: str, branch: str, marker: str) -> None: ...
    def ensure_check(self, run: dict[str, Any], conclusion: str, output: dict[str, str]) -> None: ...


class AppProjection:
    """Runtime adapter that makes one durable, App-owned follow-up per proposal.

    The follow-up record is written before every remote mutation.  A retry
    therefore adopts a branch or PR by its stable proposal marker instead of
    issuing another author-branch write or another pull request.
    """

    def __init__(self, store: Any, gateway: ProjectionGateway) -> None:
        self.store = store
        self.gateway = gateway

    def head_is_current(self, run: dict[str, Any]) -> bool:
        try:
            current = _pull_identity(self.gateway.pull_request(copy.deepcopy(run)))
            expected = run["assignment"]["identity"]["head_sha"]
            return current is not None and current["head_sha"] == expected
        except (KeyError, TypeError, ValueError):
            return False

    def perform(self, action: str, run: dict[str, Any]) -> None:
        if action == "dispatch":
            return
        review = ((run.get("candidate") or {}).get("artifact"))
        if action == "ensure_check":
            self.gateway.ensure_check(run, "in_progress", {
                "title": "Documentation impact: reviewing",
                "summary": "Documentation review is in progress for this pull request revision.",
            })
            return
        if action == "ensure_stale_check":
            self.gateway.ensure_check(run, "action_required", {
                "title": "Documentation impact: stale revision",
                "summary": "This review was invalidated because the pull request revision is no longer current.",
            })
            return
        if action != "ensure_terminal_check":
            raise ValueError(f"unknown docs impact projection action: {action}")
        followup = None
        conclusion = str(run.get("conclusion") or "action_required")
        if isinstance(review, dict) and review.get("verdict") == "proposal-ready":
            try:
                followup = self._reconcile_followup(run, review)
            except Exception:  # noqa: BLE001 - projection failures must complete the visible Check
                # Intent is already durable before every branch/PR mutation.
                # Never leave the visible Check in progress when a retryable
                # projection operation fails or discovers a stale head.
                conclusion = "action_required"
                prior = run.get("followup") if isinstance(run.get("followup"), dict) else {}
                self._save_intent(run, {**prior, "state": "action-required"})
        if not self.head_is_current(run):
            self._mark_stale(run)
            self.gateway.ensure_check(run, "action_required", {
                "title": "Documentation impact: stale revision",
                "summary": "This review was invalidated because the pull request revision is no longer current.",
            })
            return
        self.gateway.ensure_check(run, conclusion, compact_check_output(review if isinstance(review, dict) else {}, followup))
        # The terminal Check itself is a mutation boundary. If the source head
        # moved after it, compensate by closing only our marker-verified
        # stacked PR and overwrite the Check with stale/action-required.
        if not self.head_is_current(run):
            self._mark_stale(run)
            self.gateway.ensure_check(run, "action_required", {
                "title": "Documentation impact: stale revision",
                "summary": "This review was invalidated because the pull request revision is no longer current.",
            })

    def _save_intent(self, run: dict[str, Any], value: dict[str, Any]) -> None:
        run["followup"] = value
        self.store.save(run)

    def _mark_stale(self, run: dict[str, Any]) -> None:
        """Compensate a source-head race without touching contributor resources."""
        followup = run.get("followup") if isinstance(run.get("followup"), dict) else {}
        number, marker, repository, branch = _text(followup.get("number")), _text(followup.get("marker")), _text(followup.get("repository")), _text(followup.get("branch"))
        if number and marker and repository and branch and followup.get("state") != "closed":
            try:
                self.gateway.close_followup(repository, number, branch, marker)
                followup = {**followup, "state": "closed"}
            except Exception:  # noqa: BLE001 - stale Check must still win if compensation is unavailable
                followup = {**followup, "state": "close-pending"}
        run["state"] = "stale"
        run["conclusion"] = "action_required"
        if followup:
            run["followup"] = followup
        self.store.save(run)

    def _reconcile_followup(self, run: dict[str, Any], review: dict[str, Any]) -> dict[str, str] | None:
        current = self.gateway.pull_request(copy.deepcopy(run))
        plan = followup_pr_plan(current, review)
        if plan is None:
            return None
        # The candidate was validated at intake; validating again here gives
        # the marker its canonical artifact digest even if a caller supplied
        # the digest-free wire representation.
        proposal = docs_patch.validate_agent_review(review)["proposal"]
        if proposal is None:
            return None
        marker = f"gas-city-docs-followup:{proposal['artifact_sha256']}"
        existing = self.gateway.find_followup(plan["repository"], plan["branch"], marker)
        if existing is not None:
            result = {"state": "created", **plan, "marker": marker, **existing}
            self._save_intent(run, result)
            return existing
        prior = run.get("followup") if isinstance(run.get("followup"), dict) else {}
        if self.gateway.branch_exists(plan["repository"], plan["branch"]):
            expected_commit = _text(prior.get("commit_sha"))
            if not expected_commit or not self.gateway.branch_matches(plan["repository"], plan["branch"], marker, expected_commit):
                return None
        else:
            self._save_intent(run, {"state": "branch-intent", **plan, "marker": marker})
            def persist_commit(commit_sha: str) -> None:
                if len(commit_sha) != 40:
                    raise ValueError("prepared App branch commit is invalid")
                self._save_intent(run, {"state": "branch-intent", **plan, "marker": marker, "commit_sha": commit_sha})
            commit_sha = self.gateway.create_branch(plan["repository"], plan["branch"], plan["head_sha"], review, marker, persist_commit)
            self._save_intent(run, {"state": "branch-created", **plan, "marker": marker, "commit_sha": commit_sha})
        persisted_followup = run.get("followup") if isinstance(run.get("followup"), dict) else {}
        if not self.gateway.branch_matches(plan["repository"], plan["branch"], marker, _text(persisted_followup.get("commit_sha"))):
            return None
        # The branch push and PR creation are separate mutation boundaries.
        # A changed contributor revision leaves the App-owned branch inert and
        # projects action-required instead of stacking onto the wrong ref.
        if followup_pr_plan(self.gateway.pull_request(copy.deepcopy(run)), review) is None:
            self._save_intent(run, {"state": "branch-created", **plan, "marker": marker, "commit_sha": _text(persisted_followup.get("commit_sha"))})
            return None
        self._save_intent(run, {"state": "pr-intent", **plan, "marker": marker, "commit_sha": _text(persisted_followup.get("commit_sha")), **({"recovered": True} if prior else {})})
        created = self.gateway.create_followup(plan["repository"], plan["branch"], plan["base"], marker, review)
        if not (_text(created.get("url")).startswith("https://") and _text(created.get("number")).isdigit()):
            raise ValueError("App-created follow-up pull request lacks URL or number")
        self._save_intent(run, {"state": "created", **plan, "marker": marker, **created})
        if not self.head_is_current(run):
            self._mark_stale(run)
            return None
        return created


class GitHubAppProjectionGateway:
    """Concrete App-only gateway; all mutations target a ``gas-city/docs-`` ref."""

    def __init__(self, app_config: dict[str, Any], installation_id: str) -> None:
        self.app_config = app_config
        self.installation_id = installation_id

    def _owner_repo(self, repository: str) -> tuple[str, str]:
        owner, repo = repository.split("/", 1)
        if not owner or not repo:
            raise ValueError("repository must be owner/name")
        return owner, repo

    def pull_request(self, run: dict[str, Any]) -> dict[str, Any]:
        identity = run["assignment"]["identity"]
        owner, repo = self._owner_repo(identity["repository"])
        return common.get_pull_request(self.app_config, self.installation_id, owner, repo, int(identity["pr_number"]))

    def _owns_followup(self, pull: dict[str, Any], repository: str, branch: str, marker: str) -> bool:
        """Require GitHub's App identity, not forgeable marker/ref text alone."""
        bot_login = common.app_bot_login(self.app_config)
        if not bot_login:
            return False
        head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
        base = pull.get("base") if isinstance(pull.get("base"), dict) else {}
        head_repo = head.get("repo") if isinstance(head.get("repo"), dict) else {}
        base_repo = base.get("repo") if isinstance(base.get("repo"), dict) else {}
        head_user = head.get("user") if isinstance(head.get("user"), dict) else {}
        return (
            _text(pull.get("body")).splitlines().count(f"<!-- {marker} -->") == 1
            and _text(head.get("ref")) == branch
            and _text(head_repo.get("full_name")) == repository
            and _text(base_repo.get("full_name")) == repository
            and _text(head_user.get("login")) == bot_login
        )

    def find_followup(self, repository: str, branch: str, marker: str) -> dict[str, str] | None:
        owner, repo = self._owner_repo(repository)
        token = common.create_installation_token(self.app_config, self.installation_id)
        response = common.github_api_paginated_list_request("GET", f"/repos/{owner}/{repo}/pulls?state=all&head={owner}:{branch}", bearer_token=token)
        for item in response:
            if isinstance(item, dict) and self._owns_followup(item, repository, branch, marker):
                return {"number": str(item.get("number", "")), "url": str(item.get("html_url", ""))}
        return None

    def branch_exists(self, repository: str, branch: str) -> bool:
        owner, repo = self._owner_repo(repository)
        token = common.create_installation_token(self.app_config, self.installation_id)
        try:
            common.github_api_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}", bearer_token=token)
        except common.GitHubAPIError as exc:
            if " 404:" in str(exc):
                return False
            raise
        return True

    def branch_matches(self, repository: str, branch: str, marker: str, commit_sha: str = "") -> bool:
        owner, repo = self._owner_repo(repository)
        token = common.create_installation_token(self.app_config, self.installation_id)
        try:
            ref = common.github_api_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch}", bearer_token=token)
            sha = str(((ref.get("object") or {}).get("sha", "")))
            if commit_sha and sha != commit_sha:
                return False
            commit = common.github_api_request("GET", f"/repos/{owner}/{repo}/git/commits/{sha}", bearer_token=token)
        except common.GitHubAPIError:
            return False
        return marker in str(((commit.get("message") or "")))

    @staticmethod
    def _git(cwd: pathlib.Path, *args: str, env: dict[str, str] | None = None) -> None:
        result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False, env=env)
        if result.returncode:
            raise common.GitHubAPIError(result.stderr.strip() or "git operation failed")

    def create_branch(self, repository: str, branch: str, head_sha: str, review: dict[str, Any], marker: str, before_push: Callable[[str], None]) -> str:
        if not branch.startswith("gas-city/docs-"):
            raise ValueError("follow-up branch is not App-owned")
        validated = docs_patch.validate_agent_review(review)
        proposal = validated["proposal"]
        if proposal is None:
            raise ValueError("follow-up requires a validated proposal")
        token = common.create_installation_token(self.app_config, self.installation_id)
        basic_auth = base64.b64encode(f"x-access-token:{token}".encode("utf-8")).decode("ascii")
        git_env = os.environ.copy()
        git_env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": f"http.{common.github_web_base().rstrip('/')}/.extraheader", "GIT_CONFIG_VALUE_0": f"AUTHORIZATION: basic {basic_auth}"})
        with tempfile.TemporaryDirectory(prefix="gas-city-docs-") as temporary:
            checkout = pathlib.Path(temporary)
            self._git(checkout, "init", "--quiet", env=git_env)
            self._git(checkout, "remote", "add", "origin", common.repository_git_url(repository), env=git_env)
            self._git(checkout, "fetch", "--depth", "1", "origin", head_sha, env=git_env)
            self._git(checkout, "checkout", "--detach", "--quiet", "FETCH_HEAD", env=git_env)
            patch = checkout / "proposal.patch"
            patch.write_text(proposal["diff"], encoding="utf-8")
            self._git(checkout, "apply", "--check", str(patch), env=git_env)
            self._git(checkout, "apply", str(patch), env=git_env)
            patch.unlink()
            self._git(checkout, "checkout", "-b", branch, env=git_env)
            self._git(checkout, "config", "user.name", "Gas City", env=git_env)
            self._git(checkout, "config", "user.email", "gas-city[bot]@users.noreply.github.com", env=git_env)
            self._git(checkout, "add", "--", *[item["path"] for item in proposal["files"]], env=git_env)
            self._git(checkout, "commit", "--quiet", "-m", f"docs: address PR #{proposal['identity']['pr_number']} review", "-m", marker, env=git_env)
            prepared = subprocess.run(["git", "rev-parse", "HEAD"], cwd=checkout, capture_output=True, text=True, check=True, env=git_env).stdout.strip()
            before_push(prepared)
            owner, repo = self._owner_repo(repository)
            current = common.get_pull_request(self.app_config, self.installation_id, owner, repo, int(proposal["identity"]["pr_number"]))
            if followup_pr_plan(current, validated) is None:
                raise common.GitHubAPIError("pull request changed before App branch push")
            common.git_push_branch(self.app_config, self.installation_id, repository, branch, cwd=str(checkout))
            return prepared

    def create_followup(self, repository: str, branch: str, base: str, marker: str, review: dict[str, Any]) -> dict[str, str]:
        owner, repo = self._owner_repo(repository)
        validated = docs_patch.validate_agent_review(review)
        proposal = validated.get("proposal")
        if proposal is None:
            raise common.GitHubAPIError("follow-up requires a validated proposal")
        current = common.get_pull_request(self.app_config, self.installation_id, owner, repo, int(proposal["identity"]["pr_number"]))
        if followup_pr_plan(current, validated) is None:
            raise common.GitHubAPIError("pull request changed before follow-up PR creation")
        created = common.create_pull_request(self.app_config, self.installation_id, owner, repo, "docs: documentation follow-up", branch, base, f"Documentation follow-up generated from a validated proposal.\n\n<!-- {marker} -->")
        return {"number": str(created.get("number", "")), "url": str(created.get("html_url", ""))}

    def close_followup(self, repository: str, number: str, branch: str, marker: str) -> None:
        owner, repo = self._owner_repo(repository)
        token = common.create_installation_token(self.app_config, self.installation_id)
        pull = common.github_api_request("GET", f"/repos/{owner}/{repo}/pulls/{number}", bearer_token=token)
        head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
        if not self._owns_followup(pull, repository, branch, marker):
            raise common.GitHubAPIError("refusing to close a follow-up not owned by this App marker")
        common.github_api_request("PATCH", f"/repos/{owner}/{repo}/pulls/{number}", payload={"state": "closed"}, bearer_token=token)

    def ensure_check(self, run: dict[str, Any], conclusion: str, output: dict[str, str]) -> None:
        identity = run["assignment"]["identity"]
        owner, repo = self._owner_repo(identity["repository"])
        if conclusion != "in_progress":
            current = common.get_pull_request(self.app_config, self.installation_id, owner, repo, int(identity["pr_number"]))
            current_identity = _pull_identity(current)
            if current_identity is None or current_identity["head_sha"] != identity["head_sha"]:
                conclusion = "action_required"
                output = {
                    "title": "Documentation impact: stale revision",
                    "summary": "This review was invalidated because the pull request revision is no longer current.",
                }
        external_id = str(run["external_id"])
        existing = common.find_check_run(self.app_config, self.installation_id, owner, repo, identity["head_sha"], external_id)
        if conclusion == "in_progress":
            if existing is None:
                run["check"] = common.create_check_run(self.app_config, self.installation_id, owner, repo, identity["head_sha"], external_id, "in_progress", None, output)
            return
        if existing is None:
            created = common.create_check_run(self.app_config, self.installation_id, owner, repo, identity["head_sha"], external_id, "completed", conclusion, output)
        else:
            created = common.update_check_run(self.app_config, self.installation_id, owner, repo, str(existing["id"]), conclusion, output)
        run["check"] = created
