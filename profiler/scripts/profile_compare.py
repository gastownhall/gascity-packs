#!/usr/bin/env python3
"""profile_compare.py — diff two profile reports (gc.profile.report.v1).

Usage: profile_compare.py <root-a> <root-b> [--city <path>]
Reads report.json from each capture (generating implies running report --json
first); prints total/wait/session deltas and per-step deltas for steps whose
titles match across the two runs.
"""
import argparse
import json
import os


def load_report(city, root):
    p = os.path.join(city, ".gc", "runtime", "profiles", root, "report.json")
    if not os.path.exists(p):
        raise SystemExit(f"missing {p} — run: gc profiler report {root} --json")
    return json.load(open(p))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("a")
    ap.add_argument("b")
    ap.add_argument("--city", default=os.environ.get("GC_CITY_PATH", ""))
    args = ap.parse_args()
    ra, rb = load_report(args.city, args.a), load_report(args.city, args.b)

    print(f"{'':<40} {'A: '+args.a:>14} {'B: '+args.b:>14} {'delta':>10}")

    def row(label, va, vb):
        d = (vb - va) if (va is not None and vb is not None) else None
        ds = f"{d:+.1f}" if d is not None else "—"
        print(f"{label:<40} {va if va is not None else '—':>14} "
              f"{vb if vb is not None else '—':>14} {ds:>10}")

    row("total wall (m)", ra["total_m"], rb["total_m"])
    row("dispatch wait (m)", ra["totals"]["dispatch_wait_m"], rb["totals"]["dispatch_wait_m"])
    row("sessions", ra["totals"]["sessions"], rb["totals"]["sessions"])
    row("session time (m)", ra["totals"]["session_time_m"], rb["totals"]["session_time_m"])
    print()

    sa = {s["title"]: s for s in ra["steps"]}
    sb = {s["title"]: s for s in rb["steps"]}
    common = [t for t in sa if t in sb]
    if common:
        print(f"{'STEP':<44} {'waitΔ':>8} {'activeΔ':>9}")
        for t in common:
            wd = (sb[t]["wait_m"] or 0) - (sa[t]["wait_m"] or 0)
            aa, ab = sa[t]["active_m"], sb[t]["active_m"]
            ad = (ab - aa) if (aa is not None and ab is not None) else None
            if abs(wd) > 0.05 or (ad is not None and abs(ad) > 0.05):
                print(f"{t[:43]:<44} {wd:>+8.1f} "
                      f"{(f'{ad:+.1f}' if ad is not None else '—'):>9}")
    only_a = [t for t in sa if t not in sb]
    only_b = [t for t in sb if t not in sa]
    if only_a:
        print(f"\nonly in A: {len(only_a)} steps")
    if only_b:
        print(f"only in B: {len(only_b)} steps")


if __name__ == "__main__":
    main()
