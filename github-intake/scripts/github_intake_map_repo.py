#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

import github_intake_common as common


def main() -> int:
    parser = argparse.ArgumentParser(description="Map a GitHub repository to the /gc fix workflow")
    parser.add_argument("repository", help="owner/repo")
    parser.add_argument("target", help="gc sling target, for example rig/polecat")
    parser.add_argument("--fix-formula", required=True, help="formula for /gc fix")
    args = parser.parse_args()

    config = common.load_config()
    config = common.set_repo_mapping(
        config,
        args.repository,
        args.target,
        args.fix_formula or None,
    )
    mapping = common.resolve_repo_mapping(config, args.repository) or {}
    print(json.dumps(mapping, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
