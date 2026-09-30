#!/usr/bin/env python3
"""Score intake routing rules against the proxy ground truth.

Tiers, from cheapest: compact (jev-build-compact), direct (jev-build without the
plan stage) and full (jev-build). Under-triage is the costly error: a
ground-truth deep change routed compact or direct, or a ground-truth standard
change routed compact.

Usage: analyze.py --set dev.json --calls calls/dev-v4 --questions v4
"""
from __future__ import annotations
import argparse
from collections import Counter
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEVELS = ('compact', 'standard', 'deep')
# compact: P(compact), max guard noul; direct: P(no design), max P(deep). Frozen 2026-09-30.
FROZEN = (0.8, 0.3, 0.9, 0.1)
# Post-test tightening (RESULTS.md): direct also excludes security and persistence surfaces.
SAFE_DIRECT = True


def facts(answers: dict) -> dict:
    size = {LEVELS[int(k)]: v for k, v in answers['size']['probabilities'].items()}
    return {'p_compact': size['compact'], 'p_deep': size['deep'],
            'size': max(size, key=size.get), 'size_confidence': answers['size']['confidence'],
            'spans_modules': answers.get('spans_modules', {}).get('noul'),
            'hidden_scope': answers.get('hidden_scope', {}).get('noul'),
            'risky_surface': answers['risky_surface']['choice'],
            'p_no_design': answers['needs_design']['probabilities'].get('no', 0.0),
            'needs_design': answers['needs_design']['choice'],
            'well_specified': answers['well_specified']['choice']}


def route_v3(f: dict, t: float) -> str:
    compact = (f['size'] == 'compact' and f['size_confidence'] >= t and f['risky_surface'] == 'none'
               and f['needs_design'] == 'no')
    return 'compact' if compact else 'full'


def route_v4(f: dict, t_compact: float, guard: float, t_direct: float, max_deep: float) -> str:
    if (f['p_compact'] >= t_compact and f['spans_modules'] <= guard and f['hidden_scope'] <= guard
            and f['risky_surface'] == 'none' and f['needs_design'] == 'no'):
        return 'compact'
    if (f['p_no_design'] >= t_direct and f['p_deep'] <= max_deep and f['spans_modules'] <= 0.5
            and (not SAFE_DIRECT or f['risky_surface'] not in ('security_or_auth', 'persistence_or_migration'))):
        return 'direct'
    return 'full'


def score(rows: list[dict], routes: list[str]) -> dict:
    out = Counter()
    for row, tier in zip(rows, routes):
        gt = row['ground_truth']['depth']
        out[f'{tier}'] += 1
        out[f'{tier}<-{gt}'] += 1
    gt_compact = sum(r['ground_truth']['depth'] == 'compact' for r in rows)
    return {'n': len(rows), 'compact': out['compact'], 'direct': out['direct'], 'full': out['full'],
            'compact_recall': f"{out['compact<-compact']}/{gt_compact}",
            'under_compact_standard': out['compact<-standard'], 'under_compact_deep': out['compact<-deep'],
            'under_direct_deep': out['direct<-deep']}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--set', required=True, type=Path)
    ap.add_argument('--calls', required=True, type=Path)
    ap.add_argument('--questions', required=True, choices=['v3', 'v4'])
    ap.add_argument('--rows', action='store_true', help='print per-record facts and routes')
    args = ap.parse_args()
    records = json.loads((HERE / args.set).read_text())['records']
    rows = []
    for r in records:
        call = json.loads((HERE / args.calls / f"{r['id']}.json").read_text())
        if call.get('ok'):
            rows.append({**r, 'facts': facts(call['body']['answers'])})
    print(f'{args.calls}: {len(rows)}/{len(records)} answered')
    if args.questions == 'v3':
        for t in (0.6, 0.8):
            print(f'v3 rule t={t}:', score(rows, [route_v3(r['facts'], t) for r in rows]))
    else:
        # FROZEN is the pre-registered rule (PROTOCOL.md); the others show sensitivity.
        for t_c, guard, t_d, deep in (FROZEN, (0.6, 0.3, 0.8, 0.2), (0.9, 0.2, 0.95, 0.05)):
            routes = [route_v4(r['facts'], t_c, guard, t_d, deep) for r in rows]
            print(f'v4 rule compact>={t_c} guards<={guard} direct>={t_d} deep<={deep}:', score(rows, routes))
    if args.rows:
        for r in rows:
            f = r['facts']
            print(f"{r['id']:>24} gt={r['ground_truth']['depth']:<8} {r['ground_truth']['changed_files']:>3}f "
                  f"{r['ground_truth']['lines']:>5}l  Pc={f['p_compact']:.2f} Pd={f['p_deep']:.2f} "
                  f"span={f['spans_modules']} hid={f['hidden_scope']} risk={f['risky_surface']} "
                  f"nodesign={f['p_no_design']:.2f}")


if __name__ == '__main__':
    main()
