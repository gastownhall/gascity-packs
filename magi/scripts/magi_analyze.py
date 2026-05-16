"""Wrapper for project_analyzer/analyze_project.sh.

Translates magi flags to PROJECT_ANALYZER_* env vars. The subprocess
receives only the positional <project_path> argument — magi flags
never reach the underlying script's argv.
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
_ANALYZER_SCRIPT: str = "analyze_project.sh"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-analyze", allow_abbrev=False)
    parser.add_argument("project_path", help="Absolute path to the project to analyze.")
    parser.add_argument("--model", default=None, help="Override PROJECT_ANALYZER_MODEL.")
    parser.add_argument("--lm-url", default=None, help="Override PROJECT_ANALYZER_LM_URL.")
    parser.add_argument("--force", action="store_true", help="Set PROJECT_ANALYZER_FORCE=1.")
    parser.add_argument("--context", default=None, help="Override PROJECT_ANALYZER_CONTEXT.")
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
    if args.model is not None: out["PROJECT_ANALYZER_MODEL"] = args.model
    if args.lm_url is not None: out["PROJECT_ANALYZER_LM_URL"] = args.lm_url
    if args.force: out["PROJECT_ANALYZER_FORCE"] = "1"
    if args.context is not None: out["PROJECT_ANALYZER_CONTEXT"] = args.context
    if args.api_token is not None: out["LM_API_TOKEN"] = args.api_token
    return out


def main() -> int:
    """Entry point for magi-analyze."""
    parser = _build_parser()
    args = parser.parse_args()
    load_pack_env()
    try:
        city_root()
        project_path = _validate_project_path(args.project_path)
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code

    load_policy("analyze")  # confirm policy constants resolve; result unused for now
    reconcile_orphans("analyze")

    analyzer = pack_root() / _ANALYZER_DIR_NAME / _ANALYZER_SCRIPT
    if not analyzer.exists() or not os.access(str(analyzer), os.X_OK):
        log_event("analyze", f"analyzer_missing path={analyzer}", level=logging.ERROR)
        return 1

    verb_log = log_path("analyze", "project")
    attach_file_log("analyze", verb_log)
    log_event("analyze", f"start project={project_path}")

    bead_id: str | None = None
    if not args.no_bd:
        bead_id = bd_create(
            title=f"magi analyze {project_path}",
            body=f"project={project_path} model={args.model} lm_url={args.lm_url}",
            labels={"pack": "magi", "verb": "analyze", "target": "project", "role": "root"},
            verb="analyze"
        )
        if bead_id: bd_update(bead_id, claim=True, verb="analyze")

    if bead_id: write_inflight_sentinel(bead_id, "analyze", "project")

    rc = 0
    closed = False
    try:
        env = os.environ.copy()
        env.update(_translated_env(args))
        with verb_log.open("a", encoding="utf-8") as handle:
            proc = subprocess.run(
                [str(analyzer), str(project_path)],
                cwd=str(analyzer.parent),
                env=env,
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False
            )
        rc = proc.returncode
        log_event("analyze", f"done rc={rc} log={verb_log}")
        if bead_id:
            outcome = "0" if rc == 0 else "1" if rc == 1 else "2" if rc == 2 else "1"
            bd_close(bead_id, outcome=outcome, verb="analyze")
            closed = True
        state = read_state()
        state["analyze"] = {
            "last_project_path": str(project_path),
            "last_run_timestamp": now_utc_iso(),
            "last_run_rc": rc,
            "last_log": str(verb_log),
            "bead_id": bead_id
        }
        write_state(state)
        return rc
    finally:
        if bead_id and not closed: bd_close(bead_id, outcome="interrupted", verb="analyze")
        if bead_id: clear_inflight_sentinel(bead_id)


if __name__ == "__main__":
    sys.exit(main())
