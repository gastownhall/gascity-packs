#!/usr/bin/env python3
"""profile_report.py — render timing analysis from a profile capture.

Formula-agnostic: derives step spans (ready -> started -> closed) from the
captured bead graph, session lanes from session beads, and totals from the
workflow root. Every figure cites captured data; nothing is estimated.

Usage:
  profile_report.py <root-id> [--city <path>] [--capture <dir>]
                    [--json] [--html] [--out <dir>]

Default output: report.txt to stdout; --json/--html write report.json /
report.html into the capture dir (or --out).
"""
import argparse
import html as html_mod
import json
import os
from datetime import datetime, timezone

SCHEMA = "gc.profile.report.v1"


def pt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def mins(a, b):
    return (b - a).total_seconds() / 60.0 if a and b else None


def load(capture):
    beads = json.load(open(os.path.join(capture, "beads.json")))
    sess_path = os.path.join(capture, "session-beads.json")
    sessions = json.load(open(sess_path)) if os.path.exists(sess_path) else []
    manifest = json.load(open(os.path.join(capture, "manifest.json")))
    return beads, sessions, manifest


def analyze(root_id, beads, session_beads):
    by_id = {b["id"]: b for b in beads}
    root = by_id[root_id]
    t0, t1 = pt(root["created_at"]), pt(root.get("closed_at"))
    total = mins(t0, t1)

    steps = []
    for b in beads:
        if b["id"] == root_id or b.get("issue_type") in ("convoy",):
            continue
        created, started, closed = pt(b.get("created_at")), pt(b.get("started_at")), pt(b.get("closed_at"))
        if not closed:
            continue
        blockers = []
        for d in b.get("dependencies") or []:
            other = d.get("depends_on_id") or d.get("id")
            if other and other in by_id and d.get("type", "blocks") == "blocks":
                blockers.append(other)
        blocker_close = [pt(by_id[x].get("closed_at")) for x in blockers]
        blocker_close = [t for t in blocker_close if t]
        ready = max([created] + blocker_close) if created else created
        wait = mins(ready, started) if (started and ready and started > ready) else 0.0
        active = mins(started, closed) if started else None
        steps.append({
            "id": b["id"], "title": b.get("title", ""),
            "type": b.get("issue_type", ""),
            "created": b.get("created_at"), "started": b.get("started_at"),
            "closed": b.get("closed_at"),
            "ready": ready.strftime("%Y-%m-%dT%H:%M:%SZ") if ready else None,
            "wait_m": round(wait, 2) if wait else 0.0,
            "active_m": round(active, 2) if active is not None else None,
            "lifecycle_m": round(mins(created, closed), 2) if created else None,
        })
    steps.sort(key=lambda s: s["started"] or s["created"] or "")

    sessions = []
    for b in session_beads:
        if b.get("issue_type") != "session":
            continue
        agent = next((l[6:] for l in (b.get("labels") or []) if l.startswith("agent:")), "?")
        name = agent.split("/")[-1]
        base, _, suffix = name.rpartition("-")
        role = base if suffix.isdigit() else name
        dur = mins(pt(b.get("created_at")), pt(b.get("closed_at")))
        sessions.append({"id": b["id"], "role": role,
                         "created": b.get("created_at"), "closed": b.get("closed_at"),
                         "duration_m": round(dur, 2) if dur else None})

    waits = sorted((s for s in steps if s["wait_m"]), key=lambda s: -s["wait_m"])
    actives = sorted((s for s in steps if s["active_m"]), key=lambda s: -s["active_m"])
    sess_total = sum(s["duration_m"] or 0 for s in sessions)

    findings = []
    total_wait = sum(s["wait_m"] for s in steps)
    if total_wait > 1:
        findings.append({
            "layer": "platform+config",
            "finding": f"{total_wait:.1f}m total dispatch wait across {sum(1 for s in steps if s['wait_m'])} "
                       f"step transitions (bead ready -> step started); largest: "
                       f"{waits[0]['title'][:60]} ({waits[0]['wait_m']:.1f}m)" if waits else "",
        })
    gates = [s for s in actives if s["active_m"] and any(
        k in s["title"].lower() for k in ("validate", "gate", "repair or block"))]
    if gates:
        findings.append({
            "layer": "formula",
            "finding": f"{sum(s['active_m'] for s in gates):.1f}m of LLM-active time in "
                       f"{len(gates)} validate/gate steps; consider [steps.check] script gates",
        })
    noops = [s for s in steps if "publish" in s["title"].lower() and (s["active_m"] or 0) > 0.5]
    for s in noops:
        findings.append({
            "layer": "formula+platform",
            "finding": f"'{s['title'][:60]}' spent {s['active_m']:.1f}m — if its outcome was knowable "
                       f"from launch vars, prune at expansion",
        })

    return {
        "schema": SCHEMA, "root": root_id,
        "window": {"start": root["created_at"], "end": root.get("closed_at")},
        "total_m": round(total, 2) if total else None,
        "totals": {
            "steps": len(steps),
            "dispatch_wait_m": round(total_wait, 2),
            "sessions": len(sessions),
            "session_time_m": round(sess_total, 2),
        },
        "steps": steps, "sessions": sessions,
        "top_waits": waits[:10], "top_active": actives[:10],
        "findings": findings,
    }


# ---------------- text ----------------
def render_text(r):
    out = []
    out.append(f"profile report {r['root']}  ({SCHEMA})")
    out.append(f"window: {r['window']['start']} -> {r['window']['end']}"
               f"   total: {r['total_m']}m")
    t = r["totals"]
    out.append(f"steps: {t['steps']}  dispatch wait: {t['dispatch_wait_m']}m  "
               f"sessions: {t['sessions']} ({t['session_time_m']}m cumulative)")
    out.append("")
    out.append(f"{'STEP':<44} {'WAIT m':>7} {'ACTIVE m':>9} {'CLOSED':>20}")
    for s in r["steps"]:
        if s["wait_m"] or s["active_m"]:
            out.append(f"{s['title'][:43]:<44} {s['wait_m']:>7.1f} "
                       f"{(s['active_m'] if s['active_m'] is not None else 0):>9.1f} "
                       f"{(s['closed'] or '')[11:19]:>20}")
    out.append("")
    out.append("findings:")
    for f in r["findings"]:
        out.append(f"  [{f['layer']}] {f['finding']}")
    return "\n".join(out)


# ---------------- html ----------------
CSS = """
:root{--surface:#fcfcfb;--page:#f9f9f7;--ink:#0b0b0b;--ink2:#52514e;--mut:#898781;
--grid:#e1e0d9;--s1:#2a78d6;--s3:#eda100;--s5:#4a3aa7;--s6:#e34948;--border:rgba(11,11,11,.10)}
@media (prefers-color-scheme: dark){:root{--surface:#1a1a19;--page:#0d0d0d;--ink:#fff;
--ink2:#c3c2b7;--grid:#2c2c2a;--s1:#3987e5;--s3:#c98500;--s5:#9085e9;--s6:#e66767;
--border:rgba(255,255,255,.10)}}
*{box-sizing:border-box}body{margin:0;background:var(--page);color:var(--ink);
font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;padding:32px 24px 64px}
main{max-width:1140px;margin:0 auto}h1{font-size:24px;margin:0 0 4px}
h2{font-size:18px;margin:36px 0 4px}.sub{color:var(--ink2);margin:0 0 12px;font-size:13.5px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 16px}
.tile .v{font-size:26px;font-weight:650}.tile .l{color:var(--ink2);font-size:13px}
figure{margin:8px 0 0;background:var(--surface);border:1px solid var(--border);border-radius:10px;
padding:16px 12px;overflow-x:auto}svg{display:block;min-width:900px;width:100%;height:auto}
.lbl{font-size:11px;fill:var(--ink2)}.dur{font-size:10.5px;fill:var(--mut)}
.tick{font-size:10px;fill:var(--mut)}.grid{stroke:var(--grid);stroke-width:1}
.act{fill:var(--s1)}.wait{fill:var(--s6)}
.legend{display:flex;gap:18px;margin:10px 4px 0;font-size:13px;color:var(--ink2)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{width:13px;height:13px;border-radius:3px;display:inline-block}
table{border-collapse:collapse;width:100%;background:var(--surface);border:1px solid var(--border);font-size:13px}
th,td{padding:6px 10px;text-align:left;border-top:1px solid var(--grid)}
th{color:var(--ink2);font-weight:600;border-top:none}.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;background:var(--page);border:1px solid var(--grid);border-radius:10px;
padding:0 8px;font-size:11.5px;color:var(--ink2);white-space:nowrap}
"""


def render_html(r):
    esc = html_mod.escape
    t0, t1 = pt(r["window"]["start"]), pt(r["window"]["end"])
    W, LBL = 1080, 250
    PW = W - LBL - 24

    def x(ts):
        return LBL + PW * (pt(ts) - t0).total_seconds() / max((t1 - t0).total_seconds(), 1)

    # gantt of steps that had a started/closed span (cap rows for sanity)
    rows, y = [], 6
    drawn = [s for s in r["steps"] if s["started"] and (s["wait_m"] or s["active_m"])]
    for s in drawn[:60]:
        ry = y
        rows.append(f'<text x="{LBL-8}" y="{ry+12}" class="lbl" text-anchor="end">{esc(s["title"][:38])}</text>')
        if s["wait_m"]:
            rows.append(f'<rect x="{x(s["ready"]):.1f}" y="{ry}" width="{max(x(s["started"])-x(s["ready"]),1.5):.1f}" height="15" rx="3" class="wait"><title>wait {s["wait_m"]:.1f}m</title></rect>')
        rows.append(f'<rect x="{x(s["started"]):.1f}" y="{ry}" width="{max(x(s["closed"])-x(s["started"]),1.5):.1f}" height="15" rx="3" class="act"><title>{esc(s["title"][:60])}: active {s["active_m"]}m</title></rect>')
        y += 21
    gantt = f'<svg viewBox="0 0 {W} {y+10}" role="img" aria-label="Step spans">{"".join(rows)}</svg>'

    # session lanes by role
    roles = {}
    for s in r["sessions"]:
        roles.setdefault(s["role"], []).append(s)
    rows, y = [], 6
    for role in sorted(roles, key=lambda k: -len(roles[k])):
        rows.append(f'<text x="{LBL-8}" y="{y+11}" class="lbl" text-anchor="end">{esc(role)} ({len(roles[role])})</text>')
        for s in roles[role]:
            if not (s["created"] and s["closed"]):
                continue
            x0 = max(x(s["created"]), LBL)
            x1v = min(x(s["closed"]), W - 20)
            rows.append(f'<rect x="{x0:.1f}" y="{y}" width="{max(x1v-x0,2):.1f}" height="13" rx="3" fill="var(--s3)" opacity=".9"><title>{esc(s["id"])} {esc(role)} {s["duration_m"]}m</title></rect>')
        y += 19
    lanes = f'<svg viewBox="0 0 {W} {y+10}" role="img" aria-label="Session lanes">{"".join(rows)}</svg>'

    step_rows = "".join(
        f"<tr><td>{esc(s['title'][:70])}</td><td class='num'>{s['wait_m']:.1f}</td>"
        f"<td class='num'>{s['active_m'] if s['active_m'] is not None else '—'}</td>"
        f"<td>{(s['closed'] or '')[11:19]}</td></tr>"
        for s in r["steps"] if s["wait_m"] or s["active_m"])
    finding_rows = "".join(
        f"<li><span class='tag'>{esc(f['layer'])}</span> {esc(f['finding'])}</li>"
        for f in r["findings"])
    t = r["totals"]
    return f"""<!doctype html><meta charset="utf-8">
<title>profile {esc(r['root'])}</title><style>{CSS}</style>
<main>
<h1>Formula run profile — <code>{esc(r['root'])}</code></h1>
<p class="sub">{esc(r['window']['start'])} → {esc(r['window']['end'])} · {SCHEMA} · generated by the profiler pack</p>
<div class="tiles">
<div class="tile"><div class="v">{r['total_m']:.1f}m</div><div class="l">total wall clock</div></div>
<div class="tile"><div class="v">{t['dispatch_wait_m']:.1f}m</div><div class="l">dispatch wait (ready→started)</div></div>
<div class="tile"><div class="v">{t['sessions']}</div><div class="l">agent sessions</div></div>
<div class="tile"><div class="v">{t['session_time_m']:.0f}m</div><div class="l">cumulative session time</div></div>
</div>
<h2>Step spans</h2>
<p class="sub">Red = dispatch wait (ready → started), blue = active. Hover for details.</p>
<figure>{gantt}</figure>
<div class="legend"><span><span class="sw" style="background:var(--s6)"></span>wait</span>
<span><span class="sw" style="background:var(--s1)"></span>active</span></div>
<h2>Agent sessions by role</h2>
<figure>{lanes}</figure>
<h2>Steps</h2>
<table><tr><th>Step</th><th class="num">Wait m</th><th class="num">Active m</th><th>Closed UTC</th></tr>{step_rows}</table>
<h2>Findings</h2>
<ul>{finding_rows}</ul>
</main>"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--city", default=os.environ.get("GC_CITY_PATH", ""))
    ap.add_argument("--capture", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--html", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    capture = args.capture or os.path.join(
        args.city, ".gc", "runtime", "profiles", args.root)
    if not os.path.isdir(capture):
        raise SystemExit(f"no capture at {capture}; run collect first")
    beads, sessions, _manifest = load(capture)
    r = analyze(args.root, beads, sessions)

    out_dir = args.out or capture
    os.makedirs(out_dir, exist_ok=True)
    if args.json:
        p = os.path.join(out_dir, "report.json")
        json.dump(r, open(p, "w"), indent=1)
        print(f"wrote {p}")
    if args.html:
        p = os.path.join(out_dir, "report.html")
        open(p, "w").write(render_html(r))
        print(f"wrote {p}")
    if not (args.json or args.html):
        print(render_text(r))
    else:
        print(render_text(r).split("\n\n")[0])


if __name__ == "__main__":
    main()
