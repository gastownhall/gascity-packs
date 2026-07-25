#!/usr/bin/env python3
"""profile_collect.py — assemble a formula-run profile capture from durable sources.

Retroactive: works on any workflow root bead id, including runs that crashed
or were never marked for profiling. Every source is read-only; failures are
recorded in the manifest, never fatal.

Usage:
  profile_collect.py <root-bead-id> [--rig <path>] [--city <path>] [--out <dir>]

Env (provided by the gc pack-command harness):
  GC_CITY_PATH  city directory (fallback for --city)

Output: <city>/.gc/runtime/profiles/<root-id>/ with manifest.json,
beads.json, session-beads.json, events.window.jsonl.gz, transcripts/*.jsonl.gz,
usage.window.jsonl, formula-provenance.json, git.json.

Capture schema: gc.profile.capture.v1
"""
import argparse
import glob
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone

SCHEMA = "gc.profile.capture.v1"
WINDOW_MARGIN_S = 120

# Metadata keys whose values link a bead into a run's closure.
# gc.var.convoy_id matters because gc.input_convoy_id gets repointed as a
# build progresses (e.g. to the implementation convoy) — the launch-time
# input convoy survives only in the runtime vars.
LINK_KEYS = (
    "gc.root_bead_id", "gc.parent_bead_id", "gc.source_bead_id",
    "gc.drain_control_id", "gc.drain_member_id", "gc.input_convoy_id",
    "gc.var.convoy_id", "gc.var.issue",
)


def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def bd_json(args, cwd):
    """Read a bead store through `gc bd`, which resolves the store from cwd.

    Bare `bd` would bypass store-aware routing (and the repo gate that enforces
    it), so every read goes through gc.
    """
    cmd = ["gc", "bd", *args]
    out = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=300)
    if out.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd)} failed: {out.stderr.strip()[:400]}")
    return json.loads(out.stdout)


def closure(all_beads, root_id):
    """Beads reachable from root via linkage metadata or dependency edges."""
    by_id = {b["id"]: b for b in all_beads}
    if root_id not in by_id:
        raise SystemExit(f"root bead {root_id} not found in rig store")
    known = {root_id}
    changed = True
    while changed:
        changed = False
        for b in all_beads:
            if b["id"] in known:
                continue
            md = b.get("metadata") or {}
            linked = any(md.get(k) in known for k in LINK_KEYS)
            if not linked:
                for d in b.get("dependencies") or []:
                    other = d.get("depends_on_id") or d.get("id")
                    if other in known:
                        linked = True
                        break
            if linked:
                known.add(b["id"])
                changed = True
        # reverse edges: beads already known may link OUT to unknown beads
        for bid in list(known):
            b = by_id.get(bid)
            if not b:
                continue
            md = b.get("metadata") or {}
            for k in LINK_KEYS:
                v = md.get(k)
                if v and v in by_id and v not in known:
                    known.add(v)
                    changed = True
            for d in b.get("dependencies") or []:
                other = d.get("depends_on_id") or d.get("id")
                if other in by_id and other not in known:
                    known.add(other)
                    changed = True
    # Sorted, not set order: the manifest hashes beads.json, so two collects of
    # the same run have to produce byte-identical output.
    return [by_id[i] for i in sorted(known)]


def project_slug(path):
    # Claude Code's slug rule: '/' AND '.' both become '-'.
    return path.replace("/", "-").replace(".", "-")


def slug_candidates(work_dir):
    absd = os.path.abspath(work_dir)
    cands = {project_slug(work_dir), project_slug(absd)}
    for pre in ("/tmp", "/var"):
        if absd.startswith(pre):
            cands.add(project_slug("/private" + absd))
        if absd.startswith("/private" + pre):
            cands.add(project_slug(absd[len("/private"):]))
    return cands


def find_transcript(work_dir, session_key, session_id=None, w0=None, w1=None):
    """Resolve a session's transcript.

    Preferred: work_dir + session_key -> <slug>/<key>.jsonl (1:1).
    Fallback (session beads often lack session_key): scan the slug dir for
    transcripts whose mtime falls in the session window and whose CONTENT
    mentions the gc session id — sessions reference their own id in env/
    claim output, making content-match the reliable join.
    """
    if not work_dir:
        return None, None
    base = os.path.expanduser("~/.claude/projects")
    for slug in slug_candidates(work_dir):
        if session_key:
            p = os.path.join(base, slug, session_key + ".jsonl")
            if os.path.exists(p):
                return p, "session_key"
    if not (session_id and w0 and w1):
        return None, None
    needle = session_id.encode()
    for slug in slug_candidates(work_dir):
        d = os.path.join(base, slug)
        if not os.path.isdir(d):
            continue
        for p in glob.glob(os.path.join(d, "*.jsonl")):
            m = datetime.fromtimestamp(os.path.getmtime(p), tz=timezone.utc)
            if not (w0 <= m <= w1 + timedelta(hours=1)):
                continue
            try:
                with open(p, "rb") as f:
                    if needle in f.read():
                        return p, "content-match"
            except OSError:
                continue
    return None, None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--rig", default=os.getcwd())
    ap.add_argument("--city", default=os.environ.get("GC_CITY_PATH", ""))
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    if not args.city:
        raise SystemExit("no city: pass --city or run via gc (GC_CITY_PATH)")
    rig = os.path.abspath(args.rig)
    city = os.path.abspath(args.city)
    out = args.out or os.path.join(city, ".gc", "runtime", "profiles", args.root)
    os.makedirs(out, exist_ok=True)
    os.makedirs(os.path.join(out, "transcripts"), exist_ok=True)

    manifest = {
        "schema": SCHEMA,
        "root": args.root,
        "rig": rig,
        "city": city,
        "collected_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {},
        "gaps": [],
    }

    # ---- beads (rig store) ----
    all_beads = bd_json(["list", "--all", "--flat", "--json"], cwd=rig)
    run_beads = closure(all_beads, args.root)
    run_beads.sort(key=lambda b: b.get("created_at") or "")
    with open(os.path.join(out, "beads.json"), "w") as f:
        json.dump(run_beads, f, indent=1)
    ids = {b["id"] for b in run_beads}
    root = next(b for b in run_beads if b["id"] == args.root)
    manifest["sources"]["beads"] = {"count": len(run_beads), "store_total": len(all_beads)}

    t0 = parse_ts(root.get("created_at"))
    t1 = parse_ts(root.get("closed_at"))
    if not t1:
        t1 = datetime.now(timezone.utc)
        manifest["gaps"].append("root not closed; window ends at collection time")
    w0 = t0 - timedelta(seconds=WINDOW_MARGIN_S)
    w1 = t1 + timedelta(seconds=WINDOW_MARGIN_S)
    manifest["window"] = {"start": w0.isoformat(), "end": w1.isoformat()}

    # ---- session + nudge beads (city store) ----
    rig_name = (root.get("metadata") or {}).get("gc.var.rig_name") or os.path.basename(rig)
    session_beads, sess_ids = [], set()
    try:
        city_beads = bd_json(
            ["list", "--all", "--include-infra", "--flat", "--json"], cwd=city)
        prefix = f"agent:{rig_name}/"
        for b in city_beads:
            labs = b.get("labels") or []
            if not any(l.startswith(prefix) for l in labs):
                continue
            c = parse_ts(b.get("created_at"))
            if c and w0 <= c <= w1:
                session_beads.append(b)
                if b.get("issue_type") == "session":
                    sess_ids.add(b["id"])
        session_beads.sort(key=lambda b: b.get("created_at") or "")
        with open(os.path.join(out, "session-beads.json"), "w") as f:
            json.dump(session_beads, f, indent=1)
        manifest["sources"]["session_beads"] = {
            "count": len(session_beads),
            "sessions": len(sess_ids),
        }
    except Exception as e:  # noqa: BLE001 - best-effort by design
        manifest["gaps"].append(f"city session beads: {e}")

    # ---- events (city log; active file + archives note) ----
    ev_path = os.path.join(city, ".gc", "events.jsonl")
    n_ev = 0
    try:
        with gzip.open(os.path.join(out, "events.window.jsonl.gz"), "wt") as ez:
            with open(ev_path) as f:
                for line in f:
                    try:
                        e = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = parse_ts(e.get("ts"))
                    if not ts or not (w0 <= ts <= w1):
                        continue
                    subj = e.get("subject", "")
                    if (subj in ids or subj in sess_ids
                            or e.get("run_id") in ids
                            or e.get("session_id") in sess_ids):
                        ez.write(line)
                        n_ev += 1
        manifest["sources"]["events"] = {"count": n_ev, "path": ev_path}
        if glob.glob(ev_path + ".archive-*.gz"):
            manifest["gaps"].append(
                "event archives exist but were not scanned (v0 reads the active log only)")
    except FileNotFoundError:
        manifest["gaps"].append(f"events log missing: {ev_path}")

    # ---- transcripts ----
    found, missed, how = 0, [], {}
    for b in session_beads:
        if b.get("issue_type") != "session":
            continue
        md = b.get("metadata") or {}
        s0 = parse_ts(b.get("created_at")) or w0
        s1 = parse_ts(b.get("closed_at")) or w1
        p, method = find_transcript(md.get("work_dir"), md.get("session_key"),
                                    b["id"], s0 - timedelta(minutes=5), s1)
        if p:
            dst = os.path.join(out, "transcripts", f"{b['id']}.jsonl.gz")
            with open(p, "rb") as src, gzip.open(dst, "wb") as dz:
                shutil.copyfileobj(src, dz)
            found += 1
            how[method] = how.get(method, 0) + 1
        else:
            missed.append(b["id"])
    manifest["sources"]["transcripts"] = {"found": found, "by": how, "missing": missed}
    if missed:
        manifest["gaps"].append(
            f"{len(missed)} session transcripts unresolved (no work_dir/session_key or file gone)")

    # ---- usage facts ----
    # Fact shape: gascity usage.Fact (internal/usage/usage.go). run_id and
    # session_id are the only bead-id-valued keys on it; step_id holds a formula
    # step id (gc.step_id), never a bead id, so it cannot be matched against the
    # closure. profile_report.py joins step_id through each step bead's
    # gc.step_id metadata instead.
    usage_path = os.path.join(city, ".gc", "usage.jsonl")
    n_use = 0
    try:
        with open(usage_path) as f, open(os.path.join(out, "usage.window.jsonl"), "w") as uo:
            for line in f:
                try:
                    u = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if u.get("run_id") in ids or u.get("session_id") in sess_ids:
                    uo.write(line)
                    n_use += 1
        manifest["sources"]["usage"] = {"count": n_use}
    except FileNotFoundError:
        manifest["gaps"].append("usage.jsonl not found")

    # ---- formula provenance ----
    md = root.get("metadata") or {}
    prov = {
        "formula": md.get("gc.formula") or root.get("title"),
        "graphv2_root_key": md.get("gc.graphv2_root_key"),
        "vars": md.get("gc.graphv2_vars.v1"),
    }
    lock = os.path.join(city, "packs.lock")
    if os.path.exists(lock):
        prov["packs_lock"] = open(lock).read()
    with open(os.path.join(out, "formula-provenance.json"), "w") as f:
        json.dump(prov, f, indent=1)

    # ---- git ----
    try:
        log = subprocess.run(
            ["git", "log", "--all", "--format=%H|%aI|%cI|%s"],
            cwd=rig, capture_output=True, text=True, timeout=60)
        commits = [dict(zip(("hash", "author_at", "commit_at", "subject"), l.split("|", 3)))
                   for l in log.stdout.strip().splitlines() if l]
        with open(os.path.join(out, "git.json"), "w") as f:
            json.dump({"commits": commits}, f, indent=1)
        manifest["sources"]["git"] = {"commits": len(commits)}
    except Exception as e:  # noqa: BLE001
        manifest["gaps"].append(f"git: {e}")

    # ---- seal ----
    files = {}
    for p in sorted(glob.glob(os.path.join(out, "**", "*"), recursive=True)):
        if os.path.isfile(p) and os.path.basename(p) != "manifest.json":
            files[os.path.relpath(p, out)] = {
                "bytes": os.path.getsize(p), "hash": sha256(p)}
    manifest["files"] = files
    with open(os.path.join(out, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=1)

    print(f"capture: {out}")
    print(f"  beads={len(run_beads)} sessions={len(sess_ids)} events={n_ev} "
          f"transcripts={found} usage={n_use} gaps={len(manifest['gaps'])}")
    for g in manifest["gaps"]:
        print(f"  gap: {g}")


if __name__ == "__main__":
    main()
