"""Status reporter for the magi pack.

Reads state.json. When bd is available, augments the report with open
pack:magi beads. Reconciles orphans before reporting so the view is
self-healing on each invocation.
"""

from __future__ import annotations

import argparse
import json
import sys

from magi_common import CLIError
from magi_common import TARGET_REGISTRY
from magi_common import bd_available_current
from magi_common import bd_list_pack
from magi_common import city_root
from magi_common import log_event
from magi_common import read_state
from magi_common import reconcile_orphans


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-status", allow_abbrev=False)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable output.")
    parser.add_argument(
        "--target",
        choices=tuple(TARGET_REGISTRY.keys()),
        default=None,
        help="Limit output to a single target."
    )
    return parser


def _build_report(target_filter: str | None) -> dict[str, object]:
    state = read_state()
    installs_raw = state.get("installs", {})
    installs: dict[str, object]
    if isinstance(installs_raw, dict):
        installs = dict(installs_raw)
    else:
        installs = {}
    if target_filter:
        installs = {target_filter: installs.get(target_filter, {})}
    report: dict[str, object] = {
        "schema_version": state.get("schema_version"),
        "pack_version": state.get("pack_version"),
        "bd_available": bd_available_current(),
        "installs": installs,
        "analyze": state.get("analyze", {}),
        "improve": state.get("improve", {}),
        "doctor": state.get("doctor", {}),
        "molecule": state.get("molecule", {}),
        "bootstrap_project": state.get("bootstrap_project", {}),
        "magi_utilities_source": state.get("magi_utilities_source"),
        "failures": state.get("failures", [])
    }
    if bd_available_current():
        open_beads = bd_list_pack(status="open", verb="status")
        report["open_beads"] = open_beads
    return report


def _print_human(report: dict[str, object]) -> None:
    print(f"magi pack — schema {report.get('schema_version')} version {report.get('pack_version')}")
    print(f"bd available: {report.get('bd_available')}")
    print(f"utilities source: {report.get('magi_utilities_source')}")
    print("")
    print("installs:")
    installs = report.get("installs", {})
    if isinstance(installs, dict):
        for target, entry in installs.items():
            if not isinstance(entry, dict):
                print(f"  {target}: <unparseable>")
                continue
            installed = entry.get("installed")
            home = entry.get("target")
            rc = entry.get("last_run_rc")
            print(f"  {target}: installed={installed} home={home} last_rc={rc}")
    open_beads = report.get("open_beads")
    if isinstance(open_beads, list):
        print("")
        print(f"open beads: {len(open_beads)}")
        for bead in open_beads:
            if isinstance(bead, dict):
                print(f"  - {bead.get('id')} {bead.get('title', '')}")


def main() -> int:
    """Entry point for magi-status."""
    parser = _build_parser()
    args = parser.parse_args()
    try:
        city_root()
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code
    reconcile_orphans("status")
    report = _build_report(args.target)
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        _print_human(report)
    log_event("status", "report_emitted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
