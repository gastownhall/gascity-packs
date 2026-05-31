#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

import github_intake_common as common


def main() -> int:
    parser = argparse.ArgumentParser(description="Push a branch via the workspace GitHub App")
    parser.add_argument("repository", help="owner/repo")
    parser.add_argument("--installation-id", required=True, help="GitHub App installation id")
    parser.add_argument("--branch", required=True, help="branch name to create or update")
    parser.add_argument("--ref", default="HEAD", help="source ref to push")
    args = parser.parse_args()

    config = common.load_config()
    app_cfg = config.get("app", {})
    if not isinstance(app_cfg, dict) or not app_cfg.get("app_id") or not app_cfg.get("private_key_pem"):
        raise SystemExit("GitHub App configuration is incomplete")
    result = common.git_push_branch(
        app_cfg,
        args.installation_id,
        args.repository,
        args.branch,
        ref=args.ref,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
