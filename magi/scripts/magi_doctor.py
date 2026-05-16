"""Doctor for the magi pack.

Discovers doctor/<name>/doctor.toml files under the pack root, invokes
each sibling check-<name>.sh script, and aggregates per the exit-code
semantics declared in guidelines/markdown_library/magi/doctor.md. Adds
a synthetic `orphaned-beads` check when bd is available.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from datetime import timezone
from pathlib import Path

from magi_common import BD_DEFAULT_TIMEOUT_SECONDS
from magi_common import CLIError
from magi_common import ORPHAN_THRESHOLD_SECONDS
from magi_common import PACK_LABEL
from magi_common import SHAKEDOWN_INTERVAL_SECONDS
from magi_common import SHAKEDOWN_TRIGGER_FILENAME
from magi_common import attach_file_log
from magi_common import bd_available_current
from magi_common import bd_close
from magi_common import bd_create
from magi_common import bd_list_pack
from magi_common import city_root
from magi_common import default_shakedown_entry
from magi_common import inflight_path
from magi_common import load_policy
from magi_common import load_pack_env
from magi_common import log_event
from magi_common import log_path
from magi_common import now_utc_iso
from magi_common import pack_root
from magi_common import read_state
from magi_common import reconcile_orphans
from magi_common import runtime_dir
from magi_common import shakedown_tunable_fingerprint
from magi_common import try_bd
from magi_common import write_state


from types import ModuleType


def _try_import_tomllib() -> ModuleType | None:
    try:
        import tomllib as mod
        return mod
    except ModuleNotFoundError:
        return None


_TOMLLIB: ModuleType | None = _try_import_tomllib()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="magi-doctor", allow_abbrev=False)
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human output.")
    parser.add_argument("--no-bd", action="store_true", help="Suppress bd integration.")
    return parser


def _parse_toml_simple(path: Path) -> dict[str, object]:
    """Parse a TOML file via tomllib when available; fall back to key=value lines."""
    if _TOMLLIB is not None:
        with path.open("rb") as handle:
            payload = _TOMLLIB.load(handle)
        if isinstance(payload, dict): return payload
        return {}
    result: dict[str, object] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("["): continue
        if "=" not in line: continue
        key, value = line.split("=", 1)
        cleaned = value.strip().strip('"').strip("'")
        result[key.strip()] = cleaned
    return result


def _discover_checks(doctor_root: Path) -> list[tuple[str, Path, Path, dict[str, object]]]:
    found: list[tuple[str, Path, Path, dict[str, object]]] = []
    if not doctor_root.is_dir(): return found
    for entry in sorted(doctor_root.iterdir()):
        if not entry.is_dir(): continue
        toml_path = entry / "doctor.toml"
        if not toml_path.is_file(): continue
        check_script = entry / f"check-{entry.name}.sh"
        if not check_script.is_file(): continue
        meta = _parse_toml_simple(toml_path)
        found.append((entry.name, toml_path, check_script, meta))
    return found


def _run_check(name: str, script: Path, verb_log: Path) -> int:
    log_event("doctor", f"check_start name={name} script={script}")
    with verb_log.open("a", encoding="utf-8") as handle:
        handle.write(f"\n----- check: {name} -----\n")
        try:
            proc = subprocess.run(
                [str(script)],
                cwd=str(script.parent),
                env=os.environ.copy(),
                stdout=handle,
                stderr=subprocess.STDOUT,
                check=False
            )
        except FileNotFoundError:
            handle.write(f"check_missing script={script}\n")
            log_event("doctor", f"check_missing name={name}", level=logging.ERROR)
            return 1
    log_event("doctor", f"check_done name={name} rc={proc.returncode}")
    return proc.returncode


def _orphan_beads_check(verb_log: Path) -> int:
    if not bd_available_current():
        with verb_log.open("a", encoding="utf-8") as handle:
            handle.write("orphaned-beads: skipped (bd unavailable)\n")
        return 0
    open_beads = bd_list_pack(status="open", verb="doctor", timeout=BD_DEFAULT_TIMEOUT_SECONDS)
    stale = 0
    now_dt = datetime.now(timezone.utc)
    for bead in open_beads:
        ts = bead.get("updated_at") or bead.get("created_at")
        if not isinstance(ts, str): continue
        try:
            bead_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        except ValueError:
            continue
        if (now_dt - bead_dt).total_seconds() > ORPHAN_THRESHOLD_SECONDS: stale += 1
    with verb_log.open("a", encoding="utf-8") as handle:
        handle.write(f"orphaned-beads: open={len(open_beads)} stale={stale}\n")
    return 2 if stale > 0 else 0


def _probe_state_roundtrip(verb_log: Path) -> dict[str, object]:
    """Probe state.json read-modify-write atomically."""
    try:
        s = read_state()
        doctor_bucket = s.setdefault("doctor", {})
        if not isinstance(doctor_bucket, dict):
            doctor_bucket = {}
            s["doctor"] = doctor_bucket
        shakedown_bucket = doctor_bucket.setdefault("shakedown", {})
        if not isinstance(shakedown_bucket, dict):
            shakedown_bucket = {}
            doctor_bucket["shakedown"] = shakedown_bucket
        shakedown_bucket["probe_at"] = now_utc_iso()
        write_state(s)
        s2 = read_state()
        doctor2 = s2.get("doctor") or {}
        if not isinstance(doctor2, dict): doctor2 = {}
        shakedown2 = doctor2.get("shakedown") or {}
        if not isinstance(shakedown2, dict): shakedown2 = {}
        probe_at = shakedown2.get("probe_at")
        rc = 0 if probe_at else 1
        detail = "ok" if rc == 0 else "missing-probe_at-after-write"
    except Exception as exc:
        rc = 1
        detail = str(exc)
    with verb_log.open("a", encoding="utf-8") as handle:
        handle.write(f"shakedown probe=state-roundtrip rc={rc} detail={detail}\n")
    return {"name": "state-roundtrip", "rc": rc, "detail": detail}


def _probe_inflight_scan(verb_log: Path) -> dict[str, object]:
    """Probe inflight sentinel directory parsing."""
    sentinels = inflight_path()
    count = 0
    parse_failures = 0
    if sentinels.is_dir():
        for sentinel in sorted(sentinels.glob("*.json")):
            count += 1
            try:
                json.loads(sentinel.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                parse_failures += 1
    with verb_log.open("a", encoding="utf-8") as handle:
        handle.write(f"shakedown probe=inflight-scan count={count} parse_failures={parse_failures}\n")
    return {"name": "inflight-scan", "rc": 0, "count": count, "parse_failures": parse_failures}


def _probe_bd_list_live(verb_log: Path) -> tuple[dict[str, object], list[str]]:
    """Probe `bd list --label pack:magi --status open` parses cleanly."""
    if not bd_available_current():
        detail = "skipped-bd-missing"
        with verb_log.open("a", encoding="utf-8") as handle:
            handle.write(f"shakedown probe=bd-list-live rc=0 detail={detail}\n")
        return {"name": "bd-list-live", "rc": 0, "detail": detail}, []
    result = try_bd(
        ["list", "--label", PACK_LABEL, "--json", "--status", "open"],
        verb="doctor"
    )
    if result is None:
        detail = "bd-call-returned-none"
        with verb_log.open("a", encoding="utf-8") as handle:
            handle.write(f"shakedown probe=bd-list-live rc=0 detail={detail}\n")
        return {"name": "bd-list-live", "rc": 0, "detail": detail}, []
    if result.returncode != 0:
        detail = f"bd-rc={result.returncode}"
        with verb_log.open("a", encoding="utf-8") as handle:
            handle.write(f"shakedown probe=bd-list-live rc=0 detail={detail}\n")
        return {"name": "bd-list-live", "rc": 0, "detail": detail}, []
    try:
        payload = json.loads(result.stdout.strip() or "[]")
    except json.JSONDecodeError:
        detail = "json-decode-failed"
        with verb_log.open("a", encoding="utf-8") as handle:
            handle.write(f"shakedown probe=bd-list-live rc=0 detail={detail}\n")
        return {"name": "bd-list-live", "rc": 0, "detail": detail}, []
    bead_ids: list[str] = []
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                bead_id = item.get("id")
                if isinstance(bead_id, str) and bead_id: bead_ids.append(bead_id)
    detail = f"count={len(bead_ids)}"
    with verb_log.open("a", encoding="utf-8") as handle:
        handle.write(f"shakedown probe=bd-list-live rc=0 detail={detail}\n")
    return {"name": "bd-list-live", "rc": 0, "detail": detail}, bead_ids


def _probe_bd_show(bead_ids: list[str], verb_log: Path) -> dict[str, object]:
    """Probe `bd show <id> --json` on the first listed bead."""
    if not bead_ids:
        detail = "skipped-no-beads"
        with verb_log.open("a", encoding="utf-8") as handle:
            handle.write(f"shakedown probe=bd-show rc=0 detail={detail}\n")
        return {"name": "bd-show", "rc": 0, "detail": detail}
    result = try_bd(["show", bead_ids[0], "--json"], verb="doctor")
    if result is None:
        detail = "bd-call-returned-none"
    elif result.returncode != 0:
        detail = f"bd-rc={result.returncode}"
    else:
        try:
            json.loads(result.stdout.strip() or "{}")
            detail = "ok"
        except json.JSONDecodeError:
            detail = "json-decode-failed"
    with verb_log.open("a", encoding="utf-8") as handle:
        handle.write(f"shakedown probe=bd-show rc=0 detail={detail}\n")
    return {"name": "bd-show", "rc": 0, "detail": detail}


def _shakedown(
    verb_log: Path,
    prior: dict[str, object],
    results: list[tuple[str, int]]
) -> dict[str, object]:
    """Run the shakedown lap when triggers fire; return updated shakedown state."""
    trigger_file = runtime_dir() / SHAKEDOWN_TRIGGER_FILENAME
    lock_path = runtime_dir() / ".shakedown.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log_event("doctor", "shakedown: skipped reason=concurrent-run")
            return prior
        current_mtime: int = Path(__file__).stat().st_mtime_ns
        current_hash: str = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        current_tunables: str = shakedown_tunable_fingerprint()
        triggers_fired: list[str] = []
        if prior.get("last_run_at") is None: triggers_fired.append("never-run")
        if prior.get("script_mtime_ns") != current_mtime or prior.get("script_sha256") != current_hash:
            triggers_fired.append("script-modified")
        if prior.get("tunable_fingerprint") != current_tunables: triggers_fired.append("tunables-changed")
        if any(rc != 0 for _, rc in results): triggers_fired.append("errors-in-run")
        if trigger_file.is_file():
            triggers_fired.append("install-trigger-file")
            trigger_file.unlink(missing_ok=True)
        last_run_at_prior = prior.get("last_run_at")
        if isinstance(last_run_at_prior, str):
            try:
                prior_dt = datetime.fromisoformat(last_run_at_prior.replace("Z", "+00:00"))
                elapsed = (datetime.now(timezone.utc) - prior_dt).total_seconds()
                if elapsed > SHAKEDOWN_INTERVAL_SECONDS: triggers_fired.append("interval-elapsed")
            except ValueError:
                pass
        if not triggers_fired:
            log_event("doctor", "shakedown: skipped reason=no-triggers")
            return prior
        log_event("doctor", f"shakedown: triggered fired={','.join(triggers_fired)}")
        roundtrip = _probe_state_roundtrip(verb_log)
        inflight = _probe_inflight_scan(verb_log)
        bd_list_result, bead_ids = _probe_bd_list_live(verb_log)
        bd_show_result = _probe_bd_show(bead_ids, verb_log)
        all_probes: list[dict[str, object]] = [roundtrip, inflight, bd_list_result, bd_show_result]
        rc_values: list[int] = []
        for probe in all_probes:
            rc_raw = probe.get("rc", 0)
            rc_values.append(rc_raw if isinstance(rc_raw, int) else 0)
        shakedown_rc = max(rc_values)
        results.append(("shakedown", shakedown_rc))
        return {
            "last_run_at": now_utc_iso(),
            "last_run_rc": shakedown_rc,
            "script_mtime_ns": current_mtime,
            "script_sha256": current_hash,
            "tunable_fingerprint": current_tunables,
            "triggers_fired": triggers_fired,
            "last_findings": all_probes
        }
    finally:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        except OSError:
            pass
        os.close(lock_fd)


def _aggregate(results: list[tuple[str, int]], exit_codes: dict[str, object]) -> int:
    raw_ok = exit_codes.get("ok", 0)
    raw_fail = exit_codes.get("fail", 1)
    raw_warn = exit_codes.get("warn", 2)
    ok_value = int(raw_ok) if isinstance(raw_ok, int) else 0
    fail_value = int(raw_fail) if isinstance(raw_fail, int) else 1
    warn_value = int(raw_warn) if isinstance(raw_warn, int) else 2
    worst = ok_value
    for _, rc in results:
        if rc == fail_value: return fail_value
        if rc == warn_value: worst = warn_value
        elif rc != ok_value and worst == ok_value: worst = fail_value
    return worst


def main() -> int:
    """Entry point for magi-doctor."""
    parser = _build_parser()
    args = parser.parse_args()
    load_pack_env()
    try:
        city_root()
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return exc.exit_code

    verb_log = log_path("doctor", "all")
    attach_file_log("doctor", verb_log)
    log_event("doctor", "start")

    prior_state = read_state()
    prior_doctor_raw = prior_state.get("doctor", {})
    prior_doctor: dict[str, object] = prior_doctor_raw if isinstance(prior_doctor_raw, dict) else {}
    prior_shakedown_raw = prior_doctor.get("shakedown")
    prior_shakedown: dict[str, object] = (
        prior_shakedown_raw if isinstance(prior_shakedown_raw, dict) else default_shakedown_entry()
    )

    policy = load_policy("doctor")
    exit_codes_raw = policy.get("exit_codes")
    exit_codes: dict[str, object] = exit_codes_raw if isinstance(exit_codes_raw, dict) else {}

    doctor_root = pack_root() / "doctor"
    checks = _discover_checks(doctor_root)
    results: list[tuple[str, int]] = []
    for name, _, script, _ in checks:
        rc = _run_check(name, script, verb_log)
        results.append((name, rc))

    shakedown_entry = _shakedown(verb_log, prior_shakedown, results)

    reconcile_orphans("doctor")

    orphan_rc = _orphan_beads_check(verb_log)
    results.append(("orphaned-beads", orphan_rc))

    summary_rc = _aggregate(results, exit_codes)
    summary = {
        "timestamp": now_utc_iso(),
        "results": [{"check": name, "rc": rc} for name, rc in results],
        "summary_rc": summary_rc,
        "log": str(verb_log)
    }

    state = read_state()
    prior_d_raw = state.get("doctor", {})
    prior_d: dict[str, object] = prior_d_raw if isinstance(prior_d_raw, dict) else {}
    prior_d.update(summary)
    prior_d["shakedown"] = shakedown_entry
    state["doctor"] = prior_d
    write_state(state)

    bead_id: str | None = None
    if not args.no_bd:
        outcome = "0" if summary_rc == 0 else "1" if summary_rc == 1 else "2"
        bead_id = bd_create(
            title="magi doctor",
            body=json.dumps(summary, indent=2, sort_keys=True),
            labels={"pack": "magi", "verb": "doctor", "target": "project", "role": "root"},
            verb="doctor"
        )
        if bead_id: bd_close(bead_id, outcome=outcome, verb="doctor")

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"magi doctor summary rc={summary_rc}")
        for name, rc in results: print(f"  {name}: rc={rc}")
    return summary_rc


if __name__ == "__main__":
    sys.exit(main())
