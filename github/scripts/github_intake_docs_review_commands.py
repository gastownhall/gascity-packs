#!/usr/bin/env python3
"""Run one deployment-neutral docs-impact lifecycle operation.

The commands write action intents to a file instead of selecting a scheduler,
queue, City target, or GitHub provider.  A deployment consumes that file with
its own adapter and invokes these commands again to converge after a restart.
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from typing import Any

import github_intake_common as common
import github_intake_docs_impact as impact
import github_intake_docs_review_runtime as runtime


class ActionFileAdapter:
    def __init__(self, actions_file: pathlib.Path, head_is_current: bool) -> None:
        self.actions_file = actions_file
        self._head_is_current = head_is_current

    def head_is_current(self, run: dict[str, Any]) -> bool:
        return self._head_is_current

    def perform(self, action: str, run: dict[str, Any]) -> None:
        self.actions_file.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        document = common.read_json(str(self.actions_file), {"actions": []})
        if not isinstance(document, dict) or not isinstance(document.get("actions"), list):
            raise ValueError("actions file must contain an actions list")
        document["actions"].append({"action": action, "identity": run["identity"], "external_id": run["external_id"], "assignment": run["assignment"] if action == "dispatch" else None})
        common.atomic_write_json(str(self.actions_file), document)


def _load(path: str) -> dict[str, Any]:
    value = json.loads(pathlib.Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("input must be a JSON object")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("intake", "candidate", "reconcile"))
    parser.add_argument("--once", action="store_true", required=True)
    parser.add_argument("--store", default=common.docs_review_runs_dir())
    parser.add_argument("--actions-file")
    parser.add_argument("--projection", choices=("github", "action-file"), default="github")
    parser.add_argument("--installation-id", default=os.environ.get("GITHUB_INSTALLATION_ID", ""))
    parser.add_argument("--assignment-file")
    parser.add_argument("--candidate-file")
    parser.add_argument("--head-is-current", choices=("true", "false"), default="true")
    parser.add_argument("--now", type=float, default=None)
    args = parser.parse_args()
    now = time.time() if args.now is None else args.now
    store = runtime.FileDocsReviewStore(args.store)
    if args.projection == "github":
        config = common.load_effective_config()
        installation_id = args.installation_id or str((config.get("app") or {}).get("installation_id", ""))
        if not installation_id:
            parser.error("GitHub projection requires --installation-id or configured app installation_id")
        adapter = impact.AppProjection(store, impact.GitHubAppProjectionGateway(config.get("app") or {}, installation_id))
    else:
        if not args.actions_file:
            parser.error("action-file projection requires --actions-file")
        adapter = ActionFileAdapter(pathlib.Path(args.actions_file), args.head_is_current == "true")
    try:
        if args.operation == "intake":
            if not args.assignment_file:
                parser.error("intake requires --assignment-file")
            result = runtime.intake_delivery(store, _load(args.assignment_file), adapter, now=now)
        elif args.operation == "candidate":
            if not args.candidate_file:
                parser.error("candidate requires --candidate-file")
            result = runtime.accept_candidate(store, _load(args.candidate_file), adapter, now=now)
        else:
            result = {"runs": runtime.reconcile_pending(store, adapter, now=now)}
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
