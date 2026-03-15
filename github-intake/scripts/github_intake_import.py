#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json

import github_intake_common as common


def main() -> int:
    parser = argparse.ArgumentParser(description="Import an existing GitHub App configuration")
    parser.add_argument("--app-id", required=True, help="GitHub App id")
    parser.add_argument("--client-id", default="", help="GitHub App client id")
    parser.add_argument("--client-secret", default="", help="GitHub App client secret")
    parser.add_argument("--webhook-secret", required=True, help="GitHub App webhook secret")
    parser.add_argument("--private-key-file", required=True, help="Path to the GitHub App private key PEM")
    parser.add_argument("--slug", default="", help="GitHub App slug")
    parser.add_argument("--html-url", default="", help="GitHub App HTML URL")
    args = parser.parse_args()

    with open(args.private_key_file, "r", encoding="utf-8") as handle:
        private_key_pem = handle.read()

    config = common.load_config()
    config = common.import_app_config(
        config,
        {
            "app_id": args.app_id,
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "webhook_secret": args.webhook_secret,
            "private_key_pem": private_key_pem,
            "slug": args.slug,
            "html_url": args.html_url,
        },
    )
    print(json.dumps(common.redact_config(config), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
