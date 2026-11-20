"""``soak <subcommand>``: the one entry to the harness. Every subcommand
checks first that it runs on the disposable soak VM (:func:`soaklib.guard`)."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Collection, Dict, List, Mapping, Optional, Sequence, Set

from soaklib import City, ProcFS, Rec, Refused, SoakPaths, append_jsonl, city_from_env, guard, run, unit_of

NOTE_COVERS: Dict[str, List[str]] = {
    "supervisor-restart": ["supervisor", "controller", "store"],
    "city-stop": ["all"],
    "city-start": ["all"],
    "reboot": ["all"],
}
"""What a planned operator action may end, for the predicates' fault cover."""

CONF_HC_VERSION = "0.1.19"
"""The pinned hc that stops a conformance run's scratch cores."""


def _city(env: Mapping[str, str], paths: SoakPaths) -> City:
    return city_from_env(env, paths)


def _print(doc: Any) -> None:
    print(json.dumps(doc, indent=2, sort_keys=True))


def cmd_city_init(args: argparse.Namespace, env: Mapping[str, str], paths: SoakPaths) -> int:
    from soakcity import InitFailed, city_init

    try:
        city = city_init(paths, args.name, args.steady, args.burst, args.mode, args.load, env)
    except InitFailed as err:
        print(f"soak city-init: {err}", file=sys.stderr)
        return 1
    print(f"city ready: {city}")
    return 0


def cmd_conf_run(args: argparse.Namespace, env: Mapping[str, str], paths: SoakPaths) -> int:
    from soakconf import conf_run
    from soakhc import Teardown, conf_teardown

    hc_bin = str(paths.pinned_hc(CONF_HC_VERSION))
    procfs = ProcFS()

    def teardown(root: str) -> Teardown:
        return conf_teardown(root, hc_bin, env, procfs)

    result = conf_run(os.path.abspath(args.entry), Path(args.out), env, teardown=teardown)
    _print(result.as_rec())
    return 0 if result.ok else 1


def cmd_profile(args: argparse.Namespace, env: Mapping[str, str], paths: SoakPaths) -> int:
    from soakprofile import profile, schedule_argv

    try:
        prof = profile(args.name)
    except LookupError as err:
        print(f"soak: {err}", file=sys.stderr)
        return 2
    if args.cmd == "profile":
        print(json.dumps(prof.as_rec(paths), sort_keys=True))
        return 0
    for argv in schedule_argv(prof, paths, env):
        print("$ " + " ".join(argv))
        if args.dry_run:
            continue
        res = run(argv, timeout=60.0)
        print((res.out + res.err).rstrip())
        if not res.ok:
            print(f"soak schedule: systemd-run exited {res.code}", file=sys.stderr)
            return 1
    return 0


def cmd_toml(args: argparse.Namespace, value: Optional[str]) -> int:
    from soakcity import TomlEditError, edit_file

    try:
        edit_file(Path(args.file), args.table, args.key, value)
    except (TomlEditError, KeyError, OSError) as err:
        print(f"soak: {err}", file=sys.stderr)
        return 1
    return 0


def cmd_phase(args: argparse.Namespace, city: City) -> int:
    from soakcity import set_phase

    print(json.dumps(set_phase(city.data, args.name, args.reconciler)))
    return 0


def cmd_note(args: argparse.Namespace, city: City) -> int:
    rec: Rec = {
        "t": time.time(),
        "kind": "note",
        "who": args.who,
        "what": args.what,
        "text": " ".join(args.text),
        "covers": NOTE_COVERS.get(args.what, []),
    }
    append_jsonl(city.file("faults.jsonl"), rec)
    print(json.dumps(rec))
    return 0


def _gc_json(city: City, argv: Sequence[str], timeout: float = 60.0) -> Optional[Rec]:
    return run(["gc", *argv], cwd=str(city.path), timeout=timeout).json()


def cmd_wait(args: argparse.Namespace, city: City) -> int:
    from soakanalysis import FT_EXACT, first_turns, incarnations
    from soakcheck import agent_records, alive_by_proc
    from soakload import STEADY, running_sessions

    deadline = time.time() + args.timeout
    procfs = ProcFS()
    if args.workflows:
        ids = [w for w in args.workflows.split(",") if w]
        closed: Dict[str, float] = {}
        t0 = time.time()
        while time.time() < deadline and len(closed) < len(ids):
            for wid in ids:
                if wid in closed:
                    continue
                res = run(["gc", "bd", "show", wid, "--json"], cwd=str(city.path), timeout=60.0)
                doc = res.json()
                if doc is None and res.out.strip().startswith("["):
                    items = json.loads(res.out)
                    doc = items[0] if items and isinstance(items[0], dict) else None
                if doc is not None and doc.get("status") == "closed":
                    closed[wid] = round(time.time() - t0, 1)
                    print(f"{wid} closed after {closed[wid]} s")
            time.sleep(5.0)
        missing = [w for w in ids if w not in closed]
        if missing:
            print(f"not closed within {args.timeout} s: {', '.join(missing)}", file=sys.stderr)
            return 1
        return 0
    if args.steady is None:
        print("soak wait: --steady N or --workflows IDS", file=sys.stderr)
        return 2
    while time.time() < deadline:
        sessions = running_sessions(_gc_json(city, ["session", "list", "--json", "--template", STEADY]), STEADY)
        ready = len(sessions) >= args.steady
        if ready and args.first_turns:
            records = agent_records(city)
            incs = incarnations((r for recs in records.values() for r in recs), alive_by_proc(procfs))
            turns = {t.inc: t for t in first_turns(incs, [], time.time())}
            live = {i.session_id: i for i in incs if i.alive}
            ready = all(sid in live and turns[live[sid].inc].status == FT_EXACT for sid in sessions)
        if ready:
            print(f"{len(sessions)} soak-steady session(s) running" + (" with their first turn" if args.first_turns else ""))
            return 0
        time.sleep(5.0)
    print(f"soak wait: not ready within {args.timeout} s", file=sys.stderr)
    return 1


def _core_snapshot(city: City) -> Rec:
    from soakhc import HcError, HcRpc, core_tuple

    procfs = ProcFS()
    snap = procfs.snapshot(os.getuid())
    try:
        core = core_tuple(str(city.path))
        status = HcRpc(core.socket).status()
    except HcError as err:
        return {"error": str(err)}
    core_info = snap.get(status.pid)
    holders = set(status.holders)
    return {
        "core": {"pid": status.pid, "start": core_info.start if core_info else None, "version": status.version},
        "holders": sorted(status.holders),
        "boxes": sorted([p.pid, p.start, p.env.get("GC_SESSION_ID", "")] for p in snap.values() if p.ppid in holders),
    }


def demand_sessions(doc: Optional[Rec]) -> Set[str]:
    """Every session, open or closed, of a template other than the always-on
    pool, from ``gc session list --json --state all``.

    gc starts and retires those seats (the demand pool, the formula
    dispatcher, the store's maintenance pool) as work comes and goes, so
    their boxes end and appear whatever else runs beside the city."""
    from soakload import STEADY, template_is

    rows = (doc or {}).get("sessions") or []
    return {
        str(row["id"])
        for row in rows
        if isinstance(row, dict) and row.get("id") and not template_is(str(row.get("template", "")), STEADY)
    }


def compare_snapshots(before: Mapping[str, Any], after: Mapping[str, Any], demand: Collection[str] = ()) -> Rec:
    """What changed between two snapshots. Boxes of the ``demand`` sessions
    are reported apart, as ``demand_churn``, and are not judged."""
    b_boxes = {(int(p), int(s)): sid for p, s, sid in before.get("boxes", [])}
    a_boxes = {(int(p), int(s)): sid for p, s, sid in after.get("boxes", [])}
    ended = sorted([p, s, sid] for (p, s), sid in b_boxes.items() if (p, s) not in a_boxes)
    new = sorted([p, s, sid] for (p, s), sid in a_boxes.items() if (p, s) not in b_boxes)
    return {
        "core_same": before.get("core") == after.get("core"),
        "core_before": before.get("core"),
        "core_after": after.get("core"),
        "boxes_kept": len(set(b_boxes) & set(a_boxes)),
        "boxes_ended": [b for b in ended if b[2] not in demand],
        "boxes_new": [b for b in new if b[2] not in demand],
        "demand_churn": {
            "ended": [b for b in ended if b[2] in demand],
            "new": [b for b in new if b[2] in demand],
        },
    }


def cmd_snapshot(args: argparse.Namespace, city: City) -> int:
    now = _core_snapshot(city)
    if args.compare is None:
        print(json.dumps(now, sort_keys=True))
        return 0 if "error" not in now else 1
    text = args.compare
    if os.path.isfile(text):
        text = Path(text).read_text(encoding="utf-8")
    sessions = _gc_json(city, ["session", "list", "--json", "--state", "all"])
    if sessions is None:
        print("soak snapshot: gc session list --json --state all gave no JSON; every box is judged", file=sys.stderr)
    diff = compare_snapshots(json.loads(text), now, demand_sessions(sessions))
    _print(diff)
    return 0 if diff["core_same"] and not diff["boxes_ended"] and not diff["boxes_new"] else 1


def cmd_hc_status(city: City) -> int:
    from soakhc import HcError, HcRpc, core_tuple

    try:
        core = core_tuple(str(city.path))
        status = HcRpc(core.socket).status()
    except HcError as err:
        print(f"soak hc-status: {err}", file=sys.stderr)
        return 1
    _print({"socket": core.socket, "session": core.session, "pid": status.pid, "version": status.version, "holders": list(status.holders), "live": status.live})
    return 0


def cmd_store(city: City) -> int:
    from soakanalysis import store_procs

    procfs = ProcFS()
    _print(
        [
            {
                "pid": p.pid,
                "start": p.start,
                "comm": p.comm,
                "argv1": p.argv1,
                "cgroup": p.cgroup,
                "unit": unit_of(p.cgroup),
                "hc_scope": "HC_SCOPE" in p.env,
                "session": p.env.get("GC_SESSION_ID", ""),
            }
            for p in store_procs(procfs.snapshot(os.getuid()), os.getuid())
        ]
    )
    return 0


def placement(city: City) -> Rec:
    from soakhc import HcError, HcRpc, core_tuple
    from soaksample import supervisor_state

    procfs = ProcFS()
    snap = procfs.snapshot(os.getuid())
    doc: Rec = {}
    try:
        core = core_tuple(str(city.path))
        status = HcRpc(core.socket).status()
    except HcError as err:
        return {"error": str(err)}
    core_info = snap.get(status.pid)
    doc["core"] = {"pid": status.pid, "unit": unit_of(core_info.cgroup) if core_info else None}
    doc["holders"] = [{"pid": h, "unit": unit_of(snap[h].cgroup) if h in snap else None} for h in status.holders]
    agents = [p for p in snap.values() if p.comm == "soak-agent" and p.env.get("GC_CITY_PATH") == str(city.path)]
    doc["agents"] = [
        {
            "pid": p.pid,
            "session": p.env.get("GC_SESSION_ID", ""),
            "unit": unit_of(p.cgroup),
            "agents_slice": "gascity-agents.slice" in p.cgroup.split("/"),
            "hc_scope": "HC_SCOPE" in p.env,
        }
        for p in sorted(agents, key=lambda a: a.pid)
    ]
    sup = supervisor_state()
    sup_info = snap.get(sup["pid"])
    doc["supervisor"] = {"pid": sup["pid"], "unit": unit_of(sup_info.cgroup) if sup_info else None}
    core_unit = doc["core"]["unit"] or ""
    doc["checks"] = {
        "core_in_hc_serve_service": core_unit.startswith("hc-serve-") and core_unit.endswith(".service"),
        "holders_in_hc_hold_service": bool(doc["holders"]) and all(str(h["unit"] or "").startswith("hc-hold-") for h in doc["holders"]),
        "agents_in_run_scopes_under_agents_slice": bool(agents)
        and all(str(a["unit"] or "").startswith("run-") and a["unit"].endswith(".scope") and a["agents_slice"] for a in doc["agents"]),
        "agents_without_hc_scope": all(not a["hc_scope"] for a in doc["agents"]),
        "supervisor_in_its_service": doc["supervisor"]["unit"] == "gascity-supervisor.service",
    }
    return doc


def cmd_orphans(args: argparse.Namespace, city: City) -> int:
    from soakanalysis import find_orphans
    from soakhc import HcError, HcRpc, core_tuple

    procfs = ProcFS()
    try:
        holders: Sequence[int] = HcRpc(core_tuple(str(city.path)).socket).status().holders
    except HcError:
        holders = []
    found = find_orphans(procfs.snapshot(os.getuid()), holders, str(city.path), args.older, os.getuid())
    _print([{"pid": p.pid, "comm": p.comm, "argv": list(p.argv[:4]), "age_s": round(p.age_s), "token16": p.env.get("GC_INSTANCE_TOKEN", "")[:4] + "…"} for p in found])
    return 1 if found else 0


def cmd_final_scan(city: City, paths: SoakPaths) -> int:
    """After the city stopped: the canary grep once more, and nothing of the city running."""
    from soakcapture import remains
    from soakcheck import canary_scan

    canary = city.file("canary").read_text(encoding="utf-8").strip()
    hits = canary_scan([paths.state_root, paths.hc_share, Path(f"/tmp/gc-herdr-core-{os.getuid()}")], canary)
    left = remains(city, ProcFS())
    _print({"canary_hits": hits, "remains": left})
    return 1 if hits or left else 0


def cmd_report(args: argparse.Namespace, paths: SoakPaths) -> int:
    from soakcheck import alive_by_proc
    from soakreport import compute, first_turn_summary, load_inputs, render_markdown

    data = paths.data_root / args.city if args.city else paths.current.resolve()
    procfs = ProcFS()
    report = compute(load_inputs(data, paths.optrace, alive_by_proc(procfs), time.time(), procfs.hz))
    if args.first_turns:
        sys.stdout.write(first_turn_summary(report))
    else:
        sys.stdout.write(render_markdown(report))
    return 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="soak", description="runtime-herdr-core soak harness (runs only on the soak VM)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("city-init")
    s.add_argument("name")
    s.add_argument("--steady", type=int, required=True)
    s.add_argument("--burst", type=int, required=True)
    s.add_argument("--mode", choices=["warn", "abort"], required=True)
    s.add_argument("--load", choices=["bringup", "soak"], required=True)
    for name in ("toml-set", "toml-del"):
        s = sub.add_parser(name)
        s.add_argument("file")
        s.add_argument("table")
        s.add_argument("key")
        if name == "toml-set":
            s.add_argument("value", help="a TOML literal, e.g. '\"v2\"' or 25")
    s = sub.add_parser("phase")
    s.add_argument("name")
    s.add_argument("--reconciler", choices=["legacy", "v2"])
    s = sub.add_parser("note")
    s.add_argument("who")
    s.add_argument("what")
    s.add_argument("text", nargs="*")
    s = sub.add_parser("wait")
    s.add_argument("--steady", type=int)
    s.add_argument("--first-turns", action="store_true")
    s.add_argument("--workflows")
    s.add_argument("--timeout", type=float, default=600.0)
    s = sub.add_parser("snapshot")
    s.add_argument("--compare")
    for name in ("hc-status", "store", "placement", "load", "probe", "sample", "capture", "guard", "final-scan"):
        sub.add_parser(name)
    s = sub.add_parser("check")
    s.add_argument("--final", action="store_true")
    s = sub.add_parser("conf-teardown")
    s.add_argument("root")
    s = sub.add_parser("conf-run", help="gc runtime check and conformance in a scratch city, removed after")
    s.add_argument("entry")
    s.add_argument("out")
    s = sub.add_parser("profile", help="a soak run's city, shape, load and halves, as JSON")
    s.add_argument("name")
    s = sub.add_parser("schedule", help="the VM timers for a soak run's switch to v2 and its end")
    s.add_argument("name")
    s.add_argument("--dry-run", action="store_true")
    s = sub.add_parser("orphans")
    s.add_argument("--older", type=float, default=600.0)
    s = sub.add_parser("drill")
    s.add_argument("name")
    s.add_argument("--settle", type=float, default=600.0)
    s = sub.add_parser("report")
    s.add_argument("--city")
    s.add_argument("--markdown", action="store_true")
    s.add_argument("--first-turns", action="store_true")
    return p


def main(argv: Sequence[str], env: Mapping[str, str]) -> int:
    args = parser().parse_args(list(argv))
    try:
        guard()
    except Refused as err:
        print(f"soak: refused: {err}", file=sys.stderr)
        return 3
    paths = SoakPaths.from_env(env)
    if args.cmd == "guard":
        print("soak: this is the soak VM")
        return 0
    if args.cmd == "city-init":
        return cmd_city_init(args, env, paths)
    if args.cmd in ("toml-set", "toml-del"):
        return cmd_toml(args, getattr(args, "value", None))
    if args.cmd == "report":
        return cmd_report(args, paths)
    if args.cmd == "conf-teardown":
        from soakhc import conf_teardown

        result = conf_teardown(os.path.abspath(args.root), str(paths.pinned_hc(CONF_HC_VERSION)), env, ProcFS())
        _print(result.as_rec())
        return 0 if result.ok else 1
    if args.cmd == "conf-run":
        return cmd_conf_run(args, env, paths)
    if args.cmd in ("profile", "schedule"):
        return cmd_profile(args, env, paths)
    try:
        city = _city(env, paths)
    except LookupError as err:
        print(f"soak: {err}", file=sys.stderr)
        return 1
    if args.cmd == "phase":
        return cmd_phase(args, city)
    if args.cmd == "note":
        return cmd_note(args, city)
    if args.cmd == "wait":
        return cmd_wait(args, city)
    if args.cmd == "snapshot":
        return cmd_snapshot(args, city)
    if args.cmd == "hc-status":
        return cmd_hc_status(city)
    if args.cmd == "store":
        return cmd_store(city)
    if args.cmd == "placement":
        doc = placement(city)
        _print(doc)
        return 0 if "error" not in doc and all(doc["checks"].values()) else 1
    if args.cmd == "load":
        from soakload import load_main

        return load_main(city)
    if args.cmd == "probe":
        from soakload import probe_main

        return probe_main(city, ProcFS())
    if args.cmd == "sample":
        from soaksample import Sampler

        Sampler(city, paths).forever()
        return 0
    if args.cmd == "check":
        from soakcheck import check_main

        return check_main(city, paths, final=args.final)
    if args.cmd == "capture":
        from soakcapture import capture

        print(capture(city, paths, "gc", ProcFS()))
        return 0
    if args.cmd == "orphans":
        return cmd_orphans(args, city)
    if args.cmd == "final-scan":
        return cmd_final_scan(city, paths)
    if args.cmd == "drill":
        from soakdrill import DrillError, drill_main

        try:
            return drill_main(city, paths, args.name, settle_s=args.settle)
        except DrillError as err:
            print(f"soak drill: {err}", file=sys.stderr)
            return 1
    print(f"soak: unknown subcommand {args.cmd}", file=sys.stderr)
    return 2
