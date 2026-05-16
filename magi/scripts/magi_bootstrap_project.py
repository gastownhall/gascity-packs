"""Bootstrap a project's .utilities/ symlink via setup_utilities.sh.

Resolves MAGI_UTILITIES_SOURCE, executes setup_utilities.sh -y against
the chosen project root (defaults to $GC_CITY_PATH), verifies the
resulting .utilities symlink, and records a bd bead labeled
verb:bootstrap-project.
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
from magi_common import magi_utilities_source
from magi_common import now_utc_iso
from magi_common import read_state
from magi_common import reconcile_orphans
from magi_common import write_inflight_sentinel
from magi_common import write_state


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-bootstrap-project", allow_abbrev=False)
    parser.add_argument(
        "project_path",
        nargs="?",
        default=None,
        help="Project root path; defaults to $GC_CITY_PATH."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--yes", action="store_true", help="Non-interactive (forwarded as -y).")
    parser.add_argument("--no-bd", action="store_true")
    return parser


def _resolve_project(raw: str | None) -> Path:
    candidate = raw or os.environ.get("GC_CITY_PATH")
    if not candidate: raise CLIError("project_path required (or set GC_CITY_PATH)", exit_code=2)
    path = Path(candidate).expanduser().resolve()
    if not path.is_dir(): raise CLIError(f"project_path is not a directory: {path}", exit_code=2)
    return path


def _verify_symlink(project: Path) -> bool:
    link = project / ".utilities"
    if not link.exists(): return False
    if not link.is_symlink() and not link.is_dir(): return False
    return True


def main() -> int:
    """Entry point for magi-bootstrap-project."""
    parser = _build_parser()
    args = parser.parse_args()
    load_pack_env()
    try:
        city_root()
        project = _resolve_project(args.project_path)
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code

    load_policy("utilities")
    reconcile_orphans("bootstrap-project")

    verb_log = log_path("bootstrap-project", "project")
    attach_file_log("bootstrap-project", verb_log)
    log_event("bootstrap-project", f"start project={project}")

    src = magi_utilities_source()
    if src is None:
        log_event(
            "bootstrap-project",
            "utilities_source_unresolved cannot bootstrap",
            level=logging.ERROR
        )
        return 2

    bead_id: str | None = None
    if not args.no_bd:
        bead_id = bd_create(
            title=f"magi bootstrap-project {project}",
            body=f"project={project} utilities={src}",
            labels={
                "pack": "magi",
                "verb": "bootstrap-project",
                "target": "project",
                "role": "root"
            },
            verb="bootstrap-project"
        )
        if bead_id: bd_update(bead_id, claim=True, verb="bootstrap-project")

    if bead_id: write_inflight_sentinel(bead_id, "bootstrap-project", "project")

    rc = 0
    closed = False
    try:
        setup = src / "setup_utilities.sh"
        argv: list[str] = [str(setup)]
        if args.yes or not args.dry_run: argv.append("-y")
        if args.dry_run: argv.append("--dry-run")
        with verb_log.open("a", encoding="utf-8") as handle:
            proc = subprocess.run(
                argv,
                cwd=str(project),
                env=os.environ.copy(),
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False
            )
        rc = proc.returncode
        log_event("bootstrap-project", f"setup_utilities_done rc={rc}")
        symlink_ok = _verify_symlink(project) if not args.dry_run else True
        if not symlink_ok and rc == 0:
            log_event(
                "bootstrap-project",
                "symlink_verification_failed despite rc=0",
                level=logging.ERROR
            )
            rc = 1

        if bead_id:
            outcome = "0" if rc == 0 else "1" if rc == 1 else "2"
            bd_close(bead_id, outcome=outcome, verb="bootstrap-project")
            closed = True

        state = read_state()
        state["bootstrap_project"] = {
            "last_project_path": str(project),
            "last_run_timestamp": now_utc_iso(),
            "last_run_rc": rc,
            "bead_id": bead_id,
            "symlink_verified": symlink_ok
        }
        write_state(state)
        return rc
    finally:
        if bead_id and not closed:
            bd_close(bead_id, outcome="interrupted", verb="bootstrap-project")
        if bead_id: clear_inflight_sentinel(bead_id)


if __name__ == "__main__":
    sys.exit(main())
