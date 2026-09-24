#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse


class GitHubAPIError(Exception):
    pass


@dataclass(frozen=True)
class GitHubRef:
    owner: str
    repo_name: str
    kind: str
    number: int

    @property
    def repo_slug(self) -> str:
        return f"{self.owner}/{self.repo_name}"

    @property
    def endpoint_kind(self) -> str:
        return "issues" if self.kind == "issue" else "pull"

    @property
    def canonical_url(self) -> str:
        return f"https://github.com/{self.repo_slug}/{self.endpoint_kind}/{self.number}"


def parse_github_url(value: str, *, expected_kind: str = "") -> GitHubRef:
    parsed = urlparse(value)
    if parsed.scheme != "https" or parsed.netloc != "github.com":
        raise GitHubAPIError("GitHub URL must start with https://github.com/")
    if parsed.params or parsed.query or parsed.fragment:
        raise GitHubAPIError("GitHub URL must not include params, query, or fragment")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 4:
        raise GitHubAPIError("GitHub URL must be /<owner>/<repo>/issues/<number> or /<owner>/<repo>/pull/<number>")
    owner, repo_name, raw_kind, raw_number = parts
    if raw_kind not in {"issues", "pull"}:
        raise GitHubAPIError("GitHub URL kind must be issues or pull")
    if not raw_number.isdigit() or int(raw_number) <= 0:
        raise GitHubAPIError("GitHub URL number must be a positive integer")

    kind = "issue" if raw_kind == "issues" else "pull"
    if expected_kind and kind != expected_kind:
        raise GitHubAPIError(f"GitHub URL must reference a {expected_kind}, got {kind}")
    return GitHubRef(owner=owner, repo_name=repo_name, kind=kind, number=int(raw_number))


def body_hash(body: str) -> str:
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def gh_api(args: list[str]) -> dict[str, Any] | list[Any]:
    result = subprocess.run(["gh", "api", *args], text=True, capture_output=True, check=False)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"gh api exited {result.returncode}"
        raise GitHubAPIError(detail)
    if not result.stdout.strip():
        return {}
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GitHubAPIError(f"gh api returned invalid JSON: {exc}") from exc
    if not isinstance(data, (dict, list)):
        raise GitHubAPIError("gh api returned JSON that is not an object or list")
    return data


def issue_snapshot(url: str) -> dict[str, Any]:
    ref = parse_github_url(url, expected_kind="issue")
    data = require_object(gh_api([f"repos/{ref.repo_slug}/issues/{ref.number}"]))
    body = string_or_empty(data.get("body"))
    return {
        "ok": True,
        "owner": ref.owner,
        "repo_name": ref.repo_name,
        "repo": ref.repo_slug,
        "kind": "issue",
        "number": ref.number,
        "canonical_url": ref.canonical_url,
        "title": string_or_empty(data.get("title")),
        "body": body,
        "body_hash": body_hash(body),
        "state": string_or_empty(data.get("state")),
        "author": nested_login(data.get("user")),
        "labels": label_names(data.get("labels")),
        "html_url": string_or_empty(data.get("html_url")) or ref.canonical_url,
        "api_url": string_or_empty(data.get("url")),
        "created_at": string_or_empty(data.get("created_at")),
        "updated_at": string_or_empty(data.get("updated_at")),
    }


def pr_snapshot(url: str) -> dict[str, Any]:
    ref = parse_github_url(url, expected_kind="pull")
    data = require_object(gh_api([f"repos/{ref.repo_slug}/pulls/{ref.number}"]))
    body = string_or_empty(data.get("body"))
    head = data.get("head") if isinstance(data.get("head"), dict) else {}
    base = data.get("base") if isinstance(data.get("base"), dict) else {}
    return {
        "ok": True,
        "owner": ref.owner,
        "repo_name": ref.repo_name,
        "repo": ref.repo_slug,
        "kind": "pull",
        "number": ref.number,
        "canonical_url": ref.canonical_url,
        "title": string_or_empty(data.get("title")),
        "body": body,
        "body_hash": body_hash(body),
        "state": string_or_empty(data.get("state")),
        "author": nested_login(data.get("user")),
        "head_sha": string_or_empty(head.get("sha")),
        "head_ref": string_or_empty(head.get("ref")),
        "head_repo": nested_full_name(head.get("repo")),
        "base_ref": string_or_empty(base.get("ref")),
        "base_repo": nested_full_name(base.get("repo")),
        "html_url": string_or_empty(data.get("html_url")) or ref.canonical_url,
        "api_url": string_or_empty(data.get("url")),
        "created_at": string_or_empty(data.get("created_at")),
        "updated_at": string_or_empty(data.get("updated_at")),
    }


def actor() -> dict[str, Any]:
    data = require_object(gh_api(["user"]))
    login = string_or_empty(data.get("login"))
    if not login:
        raise GitHubAPIError("authenticated GitHub actor did not include login")
    return {"ok": True, "login": login}


def comment_create(url: str, body_path: Path) -> dict[str, Any]:
    ref = parse_github_url(url)
    body = body_path.read_text(encoding="utf-8")
    data = require_object(gh_api(["-X", "POST", f"repos/{ref.repo_slug}/issues/{ref.number}/comments", "-f", f"body={body}"]))
    return normalize_comment(data)


def comment_update(repo_slug: str, comment_id: int, body_path: Path) -> dict[str, Any]:
    validate_repo_slug(repo_slug)
    if comment_id <= 0:
        raise GitHubAPIError("comment id must be a positive integer")
    body = body_path.read_text(encoding="utf-8")
    data = require_object(gh_api(["-X", "PATCH", f"repos/{repo_slug}/issues/comments/{comment_id}", "-f", f"body={body}"]))
    return normalize_comment(data)


def pr_create(
    repo_slug: str,
    *,
    head: str,
    base: str,
    title_path: Path,
    body_path: Path,
    draft: bool = False,
) -> dict[str, Any]:
    validate_repo_slug(repo_slug)
    title = read_title(title_path)
    body = body_path.read_text(encoding="utf-8")
    data = require_object(
        gh_api(
            [
                "-X",
                "POST",
                f"repos/{repo_slug}/pulls",
                "-f",
                f"head={head}",
                "-f",
                f"base={base}",
                "-f",
                f"title={title}",
                "-f",
                f"body={body}",
                "-F",
                f"draft={str(draft).lower()}",
            ]
        )
    )
    return normalize_pr(data)


def pr_update(pr_url: str, title_path: Path, body_path: Path) -> dict[str, Any]:
    ref = parse_github_url(pr_url, expected_kind="pull")
    title = read_title(title_path)
    body = body_path.read_text(encoding="utf-8")
    data = require_object(
        gh_api(["-X", "PATCH", f"repos/{ref.repo_slug}/pulls/{ref.number}", "-f", f"title={title}", "-f", f"body={body}"])
    )
    return normalize_pr(data)


def pr_search(repo_slug: str, marker: str, *, author: str = "") -> dict[str, Any]:
    validate_repo_slug(repo_slug)
    query = f'repo:{repo_slug} type:pr is:open "{marker}"'
    if author:
        query += f" author:{author}"
    data = require_object(gh_api([f"search/issues?q={quote(query, safe=': /')}"]))
    items = data.get("items", [])
    if not isinstance(items, list):
        raise GitHubAPIError("search response items must be a list")
    normalized = []
    for item in items:
        if isinstance(item, dict):
            normalized.append(
                {
                    "number": int_or_zero(item.get("number")),
                    "title": string_or_empty(item.get("title")),
                    "url": string_or_empty(item.get("html_url")),
                    "author": nested_login(item.get("user")),
                    "state": string_or_empty(item.get("state")),
                }
            )
    return {"ok": True, "repo": repo_slug, "marker": marker, "author": author, "items": normalized}


def normalize_comment(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "id": int_or_zero(data.get("id")),
        "node_id": string_or_empty(data.get("node_id")),
        "url": string_or_empty(data.get("html_url")),
        "api_url": string_or_empty(data.get("url")),
        "author": nested_login(data.get("user")),
        "created_at": string_or_empty(data.get("created_at")),
        "updated_at": string_or_empty(data.get("updated_at")),
    }


def normalize_pr(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "ok": True,
        "number": int_or_zero(data.get("number")),
        "url": string_or_empty(data.get("html_url")),
        "api_url": string_or_empty(data.get("url")),
        "state": string_or_empty(data.get("state")),
        "draft": bool(data.get("draft", False)),
        "author": nested_login(data.get("user")),
    }


def label_names(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    names: list[str] = []
    for item in value:
        if isinstance(item, dict):
            name = string_or_empty(item.get("name"))
            if name:
                names.append(name)
        elif isinstance(item, str) and item.strip():
            names.append(item.strip())
    return names


def nested_login(value: Any) -> str:
    return string_or_empty(value.get("login")) if isinstance(value, dict) else ""


def nested_full_name(value: Any) -> str:
    return string_or_empty(value.get("full_name")) if isinstance(value, dict) else ""


def int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def string_or_empty(value: Any) -> str:
    return value if isinstance(value, str) else ""


def require_object(value: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise GitHubAPIError("expected GitHub API object response")
    return value


def validate_repo_slug(value: str) -> None:
    parts = value.split("/")
    if len(parts) != 2 or not all(parts):
        raise GitHubAPIError("repo must be owner/repo")


def read_title(path: Path) -> str:
    title = path.read_text(encoding="utf-8").strip()
    if not title:
        raise GitHubAPIError("title file must not be empty")
    return title


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GitHub API wrapper for gc workflows")
    subparsers = parser.add_subparsers(dest="command", required=True)

    parse_url_parser = subparsers.add_parser("parse-url")
    parse_url_parser.add_argument("url")
    parse_url_parser.add_argument("--kind", choices=["issue", "pull"], default="")

    issue_parser = subparsers.add_parser("issue-snapshot")
    issue_parser.add_argument("url")

    pr_parser = subparsers.add_parser("pr-snapshot")
    pr_parser.add_argument("url")

    subparsers.add_parser("actor")

    comment_create_parser = subparsers.add_parser("comment-create")
    comment_create_parser.add_argument("url")
    comment_create_parser.add_argument("--body-file", type=Path, required=True)

    comment_update_parser = subparsers.add_parser("comment-update")
    comment_update_parser.add_argument("--repo", required=True)
    comment_update_parser.add_argument("--comment-id", type=int, required=True)
    comment_update_parser.add_argument("--body-file", type=Path, required=True)

    pr_create_parser = subparsers.add_parser("pr-create")
    pr_create_parser.add_argument("--repo", required=True)
    pr_create_parser.add_argument("--head", required=True)
    pr_create_parser.add_argument("--base", required=True)
    pr_create_parser.add_argument("--title-file", type=Path, required=True)
    pr_create_parser.add_argument("--body-file", type=Path, required=True)
    pr_create_parser.add_argument("--draft", action="store_true")

    pr_update_parser = subparsers.add_parser("pr-update")
    pr_update_parser.add_argument("pr_url")
    pr_update_parser.add_argument("--title-file", type=Path, required=True)
    pr_update_parser.add_argument("--body-file", type=Path, required=True)

    pr_search_parser = subparsers.add_parser("pr-search")
    pr_search_parser.add_argument("--repo", required=True)
    pr_search_parser.add_argument("--marker", required=True)
    pr_search_parser.add_argument("--author", default="")
    return parser.parse_args(argv)


def ref_to_json(ref: GitHubRef) -> dict[str, Any]:
    return {
        "ok": True,
        "owner": ref.owner,
        "repo_name": ref.repo_name,
        "repo": ref.repo_slug,
        "kind": ref.kind,
        "number": ref.number,
        "canonical_url": ref.canonical_url,
    }


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        if args.command == "parse-url":
            output = ref_to_json(parse_github_url(args.url, expected_kind=args.kind))
        elif args.command == "issue-snapshot":
            output = issue_snapshot(args.url)
        elif args.command == "pr-snapshot":
            output = pr_snapshot(args.url)
        elif args.command == "actor":
            output = actor()
        elif args.command == "comment-create":
            output = comment_create(args.url, args.body_file)
        elif args.command == "comment-update":
            output = comment_update(args.repo, args.comment_id, args.body_file)
        elif args.command == "pr-create":
            output = pr_create(
                args.repo,
                head=args.head,
                base=args.base,
                title_path=args.title_file,
                body_path=args.body_file,
                draft=args.draft,
            )
        elif args.command == "pr-update":
            output = pr_update(args.pr_url, args.title_file, args.body_file)
        elif args.command == "pr-search":
            output = pr_search(args.repo, args.marker, author=args.author)
        else:  # pragma: no cover
            raise GitHubAPIError(f"unsupported command {args.command}")
    except (OSError, GitHubAPIError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
