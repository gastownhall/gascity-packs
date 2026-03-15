#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

import github_intake_common as common


def main() -> int:
    parser = argparse.ArgumentParser(description="Map a GitHub repository to slash-command dispatch")
    parser.add_argument("repository", help="owner/repo")
    parser.add_argument("target", help="gc sling target, for example rig/polecat")
    parser.add_argument("--review-formula", default="", help="formula for /gc review")
    parser.add_argument("--question-formula", default="", help="formula for /gc question")
    parser.add_argument("--fix-formula", default="", help="formula for /gc fix")
    args = parser.parse_args()

    if not args.review_formula and not args.question_formula and not args.fix_formula:
        parser.error("at least one command formula is required")

    config = common.load_config()
    config = common.set_repo_mapping(
        config,
        args.repository,
        args.target,
        args.review_formula or None,
        args.question_formula or None,
        args.fix_formula or None,
    )
    mapping = common.resolve_repo_mapping(config, args.repository) or {}
    print(json.dumps(mapping, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
