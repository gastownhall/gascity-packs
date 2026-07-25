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

# Usage facts follow gascity's usage.Fact (internal/usage/usage.go). Two of its
# properties drive the rollup below and are easy to get wrong:
#   - facts carry an idempotency_key precisely because they can be re-emitted,
#     so they must be deduped on it (gascity's own reader, usage.ReadFacts in
#     internal/usage/local_sink.go, does the same);
#   - step_id is the *formula* step id (gc.step_id), not a bead id, so per-step
#     attribution has to join through each step bead's gc.step_id metadata.
TOKEN_FIELDS = ("input_tokens", "output_tokens",
                "cache_read_tokens", "cache_creation_tokens")


def pt(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ") if t else None


def mins(a, b):
    return (b - a).total_seconds() / 60.0 if a and b else None


def fmt_m(v):
    return f"{v:.1f}m" if v is not None else "—"


def load(capture):
    beads = json.load(open(os.path.join(capture, "beads.json")))
    sess_path = os.path.join(capture, "session-beads.json")
    sessions = json.load(open(sess_path)) if os.path.exists(sess_path) else []
    manifest = json.load(open(os.path.join(capture, "manifest.json")))
    return beads, sessions, manifest


# ---------------- usage rollup ----------------
def read_usage(capture):
    """Load captured usage facts. Returns (facts, malformed_line_count).

    A missing usage.window.jsonl is not an error and returns (None, 0): the city
    may run with its usage sink set to discard or exec, in which case there are
    no local facts to capture. Duplicates are collapsed on idempotency_key so a
    re-emitted fact cannot double-count.
    """
    path = os.path.join(capture, "usage.window.jsonl")
    if not os.path.exists(path):
        return None, 0
    facts, seen, malformed = [], set(), 0
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                fact = json.loads(line)
            except json.JSONDecodeError:
                malformed += 1
                continue
            if not isinstance(fact, dict):
                malformed += 1
                continue
            key = fact.get("idempotency_key")
            if key:
                if key in seen:
                    continue
                seen.add(key)
            facts.append(fact)
    return facts, malformed


def usage_acc():
    acc = {"model_facts": 0, "compute_facts": 0, "unpriced_facts": 0,
           "wall_s": 0.0, "cost_usd": 0.0}
    acc.update({k: 0 for k in TOKEN_FIELDS})
    return acc


def num(fact, key, cast):
    try:
        return cast(fact.get(key) or 0)
    except (TypeError, ValueError):
        return cast(0)


def add_fact(acc, fact):
    """Fold one usage fact into an accumulator, matching `gc costs` semantics.

    A pricing miss (unpriced) is counted and its cost left out of the total
    rather than read as a free invocation — cmd/gc/cmd_costs.go does the same,
    and the usage-facts design is explicit that a rollup which hides unpriced
    facts silently undercounts.
    """
    kind = fact.get("kind")
    if kind == "model":
        acc["model_facts"] += 1
        for k in TOKEN_FIELDS:
            acc[k] += num(fact, k, int)
        if fact.get("unpriced"):
            acc["unpriced_facts"] += 1
        else:
            acc["cost_usd"] += num(fact, "cost_usd_estimate", float)
    elif kind == "compute":
        acc["compute_facts"] += 1
        acc["wall_s"] += num(fact, "wall_seconds", float)


def seal_acc(acc):
    acc["cost_usd"] = round(acc["cost_usd"], 4)
    acc["wall_s"] = round(acc["wall_s"], 1)
    return acc


def rollup_usage(facts, malformed, steps):
    """Roll usage facts up per run and per step, and annotate each step in place.

    Per-step attribution is only claimed when the gc.step_id join is
    unambiguous. A fact with no step_id (ad-hoc, manual and idle sessions, plus
    compute facts emitted after the active-work pointer is cleared at teardown)
    or one whose step id matches more than one captured bead stays run-level and
    is reported as unattributed, rather than being spread over candidates by
    guesswork.
    """
    if facts is None:
        return {"present": False,
                "reason": "usage.window.jsonl not in capture (city usage sink "
                          "disabled or forwarded out of process)"}
    by_key = {}
    for s in steps:
        if s.get("step_key"):
            by_key.setdefault(s["step_key"], []).append(s["id"])
    run, unattributed, per_step, ambiguous = usage_acc(), usage_acc(), {}, set()
    for fact in facts:
        add_fact(run, fact)
        ids = by_key.get((fact.get("step_id") or "").strip()) or []
        if len(ids) == 1:
            add_fact(per_step.setdefault(ids[0], usage_acc()), fact)
        else:
            if len(ids) > 1:
                ambiguous.add(fact["step_id"].strip())
            add_fact(unattributed, fact)
    for s in steps:
        s["usage"] = seal_acc(per_step.get(s["id"]) or usage_acc())
    return {
        "present": True,
        "facts": len(facts),
        "malformed_lines": malformed,
        "ambiguous_step_ids": sorted(ambiguous),
        "run": seal_acc(run),
        "unattributed": seal_acc(unattributed),
    }


def usage_notes(u):
    """The caveats a cost total must never be read without."""
    notes = []
    run, un = u["run"], u["unattributed"]
    if run["unpriced_facts"]:
        notes.append(f"{run['unpriced_facts']} model fact(s) had no pricing and are "
                     f"excluded from the estimate — not measured, not free")
    if un["model_facts"] or un["compute_facts"]:
        notes.append(f"{un['model_facts']} model + {un['compute_facts']} compute fact(s) "
                     f"resolved to no captured step; run total only")
    if u["ambiguous_step_ids"]:
        notes.append(f"{len(u['ambiguous_step_ids'])} step id(s) matched more than one "
                     f"captured bead; their facts stayed run-level")
    if u["malformed_lines"]:
        notes.append(f"{u['malformed_lines']} malformed usage line(s) skipped")
    notes.append("cost is a list-price estimate for decision support, not a charge")
    return notes


def analyze(root_id, beads, session_beads, usage_facts=None, usage_malformed=0):
    by_id = {b["id"]: b for b in beads}
    root = by_id[root_id]
    t0, t1 = pt(root["created_at"]), pt(root.get("closed_at"))
    total = mins(t0, t1)
    # A run still going (or one that crashed) has no closed_at. For a retroactive
    # profiler that is a first-class case, not an error.
    in_flight = t1 is None

    steps = []
    for b in beads:
        if b["id"] == root_id or b.get("issue_type") in ("convoy",):
            continue
        created, started, closed = pt(b.get("created_at")), pt(b.get("started_at")), pt(b.get("closed_at"))
        # Started-but-unclosed steps stay in: they are what an in-flight run has
        # to show. A step with neither timestamp has no span to report.
        if not (closed or started):
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
        active = mins(started, closed) if (started and closed) else None
        md = b.get("metadata") or {}
        steps.append({
            "id": b["id"], "title": b.get("title", ""),
            "type": b.get("issue_type", ""),
            "step_key": (md.get("gc.step_id") or "").strip() or None,
            "created": b.get("created_at"), "started": b.get("started_at"),
            "closed": b.get("closed_at"),
            "in_flight": bool(started and not closed),
            "ready": iso(ready),
            "wait_m": round(wait, 2) if wait else 0.0,
            "active_m": round(active, 2) if active is not None else None,
            "lifecycle_m": round(mins(created, closed), 2) if (created and closed) else None,
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

    # Anchor the time axis on the latest timestamp the capture actually observed,
    # not on wall clock, so an in-flight report rendered days after collection
    # still frames the run instead of squashing it into a sliver.
    observed = [t for t in
                [pt(s[k]) for s in steps for k in ("closed", "started", "created")]
                + [pt(s[k]) for s in sessions for k in ("closed", "created")]
                if t]
    end_eff = t1 or (max(observed) if observed else t0)
    elapsed = mins(t0, end_eff)

    r = {
        "schema": SCHEMA, "root": root_id,
        "in_flight": in_flight,
        "window": {"start": root["created_at"], "end": root.get("closed_at"),
                   "end_effective": iso(end_eff)},
        "total_m": round(total, 2) if total is not None else None,
        "elapsed_m": round(elapsed, 2) if elapsed is not None else None,
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
    r["usage"] = rollup_usage(usage_facts, usage_malformed, steps)
    return r


# ---------------- text ----------------
def render_text(r):
    out = []
    out.append(f"profile report {r['root']}  ({SCHEMA})")
    if r.get("in_flight"):
        out.append(f"window: {r['window']['start']} -> IN FLIGHT (root not closed; "
                   f"latest observed {r['window']['end_effective']})"
                   f"   elapsed: {fmt_m(r['elapsed_m'])}")
    else:
        out.append(f"window: {r['window']['start']} -> {r['window']['end']}"
                   f"   total: {fmt_m(r['total_m'])}")
    t = r["totals"]
    out.append(f"steps: {t['steps']}  dispatch wait: {t['dispatch_wait_m']}m  "
               f"sessions: {t['sessions']} ({t['session_time_m']}m cumulative)")
    u = r.get("usage") or {}
    if u.get("present"):
        run = u["run"]
        out.append(f"tokens: in {run['input_tokens']} out {run['output_tokens']} "
                   f"cache-read {run['cache_read_tokens']} cache-write {run['cache_creation_tokens']}"
                   f"   est cost: ${run['cost_usd']:.4f}"
                   f"   runtime wall: {run['wall_s']:.1f}s")
    else:
        out.append(f"tokens/cost: not captured — {u.get('reason', 'no usage data')}")
    out.append("")
    out.append(f"{'STEP':<44} {'WAIT m':>7} {'ACTIVE m':>9} {'CLOSED':>20}")
    for s in r["steps"]:
        if s["wait_m"] or s["active_m"] or s.get("in_flight"):
            active = (f"{s['active_m']:>9.1f}" if s["active_m"] is not None
                      else f"{'running':>9}")
            out.append(f"{s['title'][:43]:<44} {s['wait_m']:>7.1f} {active} "
                       f"{((s['closed'] or '')[11:19] or '—'):>20}")
    if u.get("present"):
        out.append("")
        out.append("cost by step (top 10):")
        priced = sorted((s for s in r["steps"] if s["usage"]["model_facts"]),
                        key=lambda s: -s["usage"]["cost_usd"])[:10]
        for s in priced:
            su = s["usage"]
            out.append(f"  {s['title'][:44]:<45} ${su['cost_usd']:>9.4f}  "
                       f"in {su['input_tokens']} out {su['output_tokens']}")
        if not priced:
            out.append("  no usage fact resolved to a captured step")
        for n in usage_notes(u):
            out.append(f"  note: {n}")
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
.act{fill:var(--s1)}.wait{fill:var(--s6)}.run{fill:var(--s5)}
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
    t0 = pt(r["window"]["start"])
    if t0 is None:
        raise SystemExit(f"root {r['root']} has no parsable created_at; "
                         f"cannot place an HTML time axis")
    # end_effective falls back to the run's own start for a just-launched root,
    # so the axis is always anchored on two real timestamps.
    t1 = pt(r["window"].get("end_effective")) or pt(r["window"]["end"]) or t0
    in_flight = bool(r.get("in_flight"))
    W, LBL = 1080, 250
    PW = W - LBL - 24
    span = max((t1 - t0).total_seconds(), 1)

    def x(ts):
        # An unclosed span runs to the end of the axis instead of crashing on None.
        return LBL + PW * ((pt(ts) or t1) - t0).total_seconds() / span

    # gantt of steps that had a started/closed span (cap rows for sanity)
    rows, y = [], 6
    drawn = [s for s in r["steps"]
             if s["started"] and (s["wait_m"] or s["active_m"] or s.get("in_flight"))]
    for s in drawn[:60]:
        ry = y
        rows.append(f'<text x="{LBL-8}" y="{ry+12}" class="lbl" text-anchor="end">{esc(s["title"][:38])}</text>')
        if s["wait_m"]:
            rows.append(f'<rect x="{x(s["ready"]):.1f}" y="{ry}" width="{max(x(s["started"])-x(s["ready"]),1.5):.1f}" height="15" rx="3" class="wait"><title>wait {s["wait_m"]:.1f}m</title></rect>')
        running = bool(s.get("in_flight"))
        cls, tip = ("run", "still running") if running else ("act", f"active {fmt_m(s['active_m'])}")
        rows.append(f'<rect x="{x(s["started"]):.1f}" y="{ry}" width="{max(x(s["closed"])-x(s["started"]),1.5):.1f}" height="15" rx="3" class="{cls}"><title>{esc(s["title"][:60])}: {tip}</title></rect>')
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
            if not s["created"]:
                continue
            x0 = max(x(s["created"]), LBL)
            # An open session, like an open step, extends to the axis end.
            x1v = min(x(s["closed"]), W - 20)
            dur = fmt_m(s["duration_m"]) if s["closed"] else "open"
            rows.append(f'<rect x="{x0:.1f}" y="{y}" width="{max(x1v-x0,2):.1f}" height="13" rx="3" fill="var(--s3)" opacity=".9"><title>{esc(s["id"])} {esc(role)} {esc(dur)}</title></rect>')
        y += 19
    lanes = f'<svg viewBox="0 0 {W} {y+10}" role="img" aria-label="Session lanes">{"".join(rows)}</svg>'

    u = r.get("usage") or {}
    has_usage = bool(u.get("present"))
    usage_head = "<th class='num'>Tokens</th><th class='num'>Est USD</th>" if has_usage else ""

    def usage_cells(s):
        if not has_usage:
            return ""
        su = s["usage"]
        toks = su["input_tokens"] + su["output_tokens"]
        return (f"<td class='num'>{toks or '—'}</td>"
                f"<td class='num'>{su['cost_usd']:.4f}</td>")

    step_rows = "".join(
        f"<tr><td>{esc(s['title'][:70])}</td><td class='num'>{s['wait_m']:.1f}</td>"
        f"<td class='num'>{s['active_m'] if s['active_m'] is not None else 'running'}</td>"
        f"<td>{(s['closed'] or '')[11:19] or '—'}</td>{usage_cells(s)}</tr>"
        for s in r["steps"] if s["wait_m"] or s["active_m"] or s.get("in_flight"))
    finding_rows = "".join(
        f"<li><span class='tag'>{esc(f['layer'])}</span> {esc(f['finding'])}</li>"
        for f in r["findings"])
    if has_usage:
        run = u["run"]
        note_rows = "".join(f"<li>{esc(n)}</li>" for n in usage_notes(u))
        usage_section = f"""<h2>Tokens and cost</h2>
<p class="sub">Rolled up from the capture's usage facts ({u['facts']} after idempotency dedup).</p>
<div class="tiles">
<div class="tile"><div class="v">{run['input_tokens'] + run['output_tokens']}</div><div class="l">in+out tokens</div></div>
<div class="tile"><div class="v">${run['cost_usd']:.4f}</div><div class="l">estimated cost (list price)</div></div>
<div class="tile"><div class="v">{run['model_facts']}</div><div class="l">model invocations</div></div>
<div class="tile"><div class="v">{run['wall_s']:.0f}s</div><div class="l">runtime wall-seconds</div></div>
</div>
<ul>{note_rows}</ul>"""
    else:
        usage_section = (f'<h2>Tokens and cost</h2><p class="sub">Not captured — '
                         f'{esc(u.get("reason", "no usage data"))}.</p>')
    t = r["totals"]
    if in_flight:
        head_tile = (f'<div class="v">{fmt_m(r["elapsed_m"])}</div>'
                     f'<div class="l">elapsed — run still in flight</div>')
        window_end = f"in flight, latest observed {r['window']['end_effective']}"
    else:
        head_tile = (f'<div class="v">{fmt_m(r["total_m"])}</div>'
                     f'<div class="l">total wall clock</div>')
        window_end = r["window"]["end"]
    return f"""<!doctype html><meta charset="utf-8">
<title>profile {esc(r['root'])}</title><style>{CSS}</style>
<main>
<h1>Formula run profile — <code>{esc(r['root'])}</code></h1>
<p class="sub">{esc(r['window']['start'])} → {esc(str(window_end))} · {SCHEMA} · generated by the profiler pack</p>
<div class="tiles">
<div class="tile">{head_tile}</div>
<div class="tile"><div class="v">{t['dispatch_wait_m']:.1f}m</div><div class="l">dispatch wait (ready→started)</div></div>
<div class="tile"><div class="v">{t['sessions']}</div><div class="l">agent sessions</div></div>
<div class="tile"><div class="v">{t['session_time_m']:.0f}m</div><div class="l">cumulative session time</div></div>
</div>
<h2>Step spans</h2>
<p class="sub">Red = dispatch wait (ready → started), blue = active, purple = still running. Hover for details.</p>
<figure>{gantt}</figure>
<div class="legend"><span><span class="sw" style="background:var(--s6)"></span>wait</span>
<span><span class="sw" style="background:var(--s1)"></span>active</span>
<span><span class="sw" style="background:var(--s5)"></span>running</span></div>
<h2>Agent sessions by role</h2>
<figure>{lanes}</figure>
<h2>Steps</h2>
<table><tr><th>Step</th><th class="num">Wait m</th><th class="num">Active m</th><th>Closed UTC</th>{usage_head}</tr>{step_rows}</table>
{usage_section}
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
    usage_facts, usage_malformed = read_usage(capture)
    r = analyze(args.root, beads, sessions, usage_facts, usage_malformed)

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
