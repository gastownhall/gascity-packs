"""Wrapper for project_analyzer/improve_project_analysis.sh.

Translates magi flags to PROJECT_ANALYZER_* env vars. The subprocess
receives only the positional <project_path> argument.
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

from magi_common import CLIError
from magi_common import attach_file_log
from magi_common import bd_close
from magi_common import bd_create
from magi_common import bd_update
from magi_common import city_root
from magi_common import clear_inflight_sentinel
from magi_common import load_policy
from magi_common import load_pack_env
from magi_common import log_event
from magi_common import log_path
from magi_common import now_utc_iso
from magi_common import pack_root
from magi_common import read_state
from magi_common import reconcile_orphans
from magi_common import write_inflight_sentinel
from magi_common import write_state


_ANALYZER_DIR_NAME: str = "project_analyzer"
_IMPROVER_SCRIPT: str = "improve_project_analysis.sh"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-improve", allow_abbrev=False)
    parser.add_argument("project_path", help="Absolute path to the project to improve.")
    parser.add_argument("--draft-model", default=None, help="Override PROJECT_ANALYZER_DRAFT_MODEL.")
    parser.add_argument("--verify-model", default=None, help="Override PROJECT_ANALYZER_VERIFY_MODEL.")
    parser.add_argument(
        "--aggregate-model",
        default=None,
        help="Override PROJECT_ANALYZER_AGGREGATE_MODEL."
    )
    parser.add_argument("--lm-url", default=None, help="Override PROJECT_ANALYZER_LM_URL.")
    parser.add_argument("--force", action="store_true", help="Set PROJECT_ANALYZER_FORCE=1.")
    parser.add_argument("--context", default=None, help="Override PROJECT_ANALYZER_CONTEXT.")
    parser.add_argument(
        "--skip-aggregate",
        action="store_true",
        help="Set PROJECT_ANALYZER_SKIP_AGGREGATE=1."
    )
    parser.add_argument(
        "--only-aggregate",
        action="store_true",
        help="Set PROJECT_ANALYZER_ONLY_AGGREGATE=1."
    )
    parser.add_argument("--resume", action="store_true", help="Set PROJECT_ANALYZER_RESUME=1.")
    parser.add_argument("--api-token", default=None, help="Override LM_API_TOKEN.")
    parser.add_argument(
        "--blocks-on",
        default=None,
        help="Comma-separated bead ids that must close before this run."
    )
    parser.add_argument("--no-bd", action="store_true", help="Suppress bd integration.")
    return parser


def _validate_project_path(raw: str) -> Path:
    path = Path(raw)
    if not path.is_absolute(): raise CLIError(f"project_path must be absolute: {raw}", exit_code=2)
    if not path.exists(): raise CLIError(f"project_path does not exist: {raw}", exit_code=2)
    if not path.is_dir(): raise CLIError(f"project_path is not a directory: {raw}", exit_code=2)
    return path.resolve()


def _translated_env(args: argparse.Namespace) -> dict[str, str]:
    out: dict[str, str] = {}
    if args.draft_model is not None: out["PROJECT_ANALYZER_DRAFT_MODEL"] = args.draft_model
    if args.verify_model is not None: out["PROJECT_ANALYZER_VERIFY_MODEL"] = args.verify_model
    if args.aggregate_model is not None: out["PROJECT_ANALYZER_AGGREGATE_MODEL"] = args.aggregate_model
    if args.lm_url is not None: out["PROJECT_ANALYZER_LM_URL"] = args.lm_url
    if args.force: out["PROJECT_ANALYZER_FORCE"] = "1"
    if args.context is not None: out["PROJECT_ANALYZER_CONTEXT"] = args.context
    if args.skip_aggregate: out["PROJECT_ANALYZER_SKIP_AGGREGATE"] = "1"
    if args.only_aggregate: out["PROJECT_ANALYZER_ONLY_AGGREGATE"] = "1"
    if args.resume: out["PROJECT_ANALYZER_RESUME"] = "1"
    if args.api_token is not None: out["LM_API_TOKEN"] = args.api_token
    return out


def main() -> int:
    """Entry point for magi-improve."""
    parser = _build_parser()
    args = parser.parse_args()
    load_pack_env()
    try:
        city_root()
        project_path = _validate_project_path(args.project_path)
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code

    load_policy("improve")
    reconcile_orphans("improve")

    improver = pack_root() / _ANALYZER_DIR_NAME / _IMPROVER_SCRIPT
    if not improver.exists() or not os.access(str(improver), os.X_OK):
        log_event("improve", f"improver_missing path={improver}", level=logging.ERROR)
        return 1

    verb_log = log_path("improve", "project")
    attach_file_log("improve", verb_log)
    log_event("improve", f"start project={project_path}")

    bead_id: str | None = None
    if not args.no_bd:
        bead_id = bd_create(
            title=f"magi improve {project_path}",
            body=f"project={project_path} draft={args.draft_model} verify={args.verify_model}",
            labels={"pack": "magi", "verb": "improve", "target": "project", "role": "root"},
            verb="improve"
        )
        if bead_id: bd_update(bead_id, claim=True, verb="improve")

    if bead_id: write_inflight_sentinel(bead_id, "improve", "project")

    rc = 0
    closed = False
    try:
        env = os.environ.copy()
        env.update(_translated_env(args))
        with verb_log.open("a", encoding="utf-8") as handle:
            proc = subprocess.run(
                [str(improver), str(project_path)],
                cwd=str(improver.parent),
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False
            )
        rc = proc.returncode
        log_event("improve", f"done rc={rc} log={verb_log}")
        if bead_id:
            outcome = "0" if rc == 0 else "1" if rc == 1 else "2" if rc == 2 else "1"
            bd_close(bead_id, outcome=outcome, verb="improve")
            closed = True
        state = read_state()
        state["improve"] = {
            "last_project_path": str(project_path),
            "last_run_timestamp": now_utc_iso(),
            "last_run_rc": rc,
            "last_log": str(verb_log),
            "bead_id": bead_id
        }
        write_state(state)
        return rc
    finally:
        if bead_id and not closed: bd_close(bead_id, outcome="interrupted", verb="improve")
        if bead_id: clear_inflight_sentinel(bead_id)


if __name__ == "__main__":
    sys.exit(main())
