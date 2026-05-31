#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

import github_intake_common as common


def split_repository(value: str) -> tuple[str, str]:
    owner, sep, repo = value.strip().partition("/")
    if not owner or not sep or not repo:
        raise SystemExit("repository must be in owner/repo format")
    return owner, repo


def read_body(args: argparse.Namespace) -> str:
    if args.body_file:
        with open(args.body_file, "r", encoding="utf-8") as handle:
            return handle.read()
    return args.body


def main() -> int:
    parser = argparse.ArgumentParser(description="Post an issue comment via the workspace GitHub App")
    parser.add_argument("repository", help="owner/repo")
    parser.add_argument("issue_number", help="GitHub issue number")
    parser.add_argument("--installation-id", required=True, help="GitHub App installation id")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--body", default="", help="comment markdown")
    group.add_argument("--body-file", default="", help="path to a markdown file")
    args = parser.parse_args()

    config = common.load_config()
    app_cfg = config.get("app", {})
    if not isinstance(app_cfg, dict) or not app_cfg.get("app_id") or not app_cfg.get("private_key_pem"):
        raise SystemExit("GitHub App configuration is incomplete")
    owner, repo = split_repository(args.repository)
    comment = common.post_issue_comment(
        app_cfg,
        args.installation_id,
        owner,
        repo,
        args.issue_number,
        read_body(args),
    )
    print(json.dumps(comment, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
