#!/usr/bin/env python3
"""Score a calls/<run> directory against prs.json ground truth using the PROTOCOL.md rule.

Usage: analyze.py calls/eval [--json results-part.json]
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
LEVELS = ['compact', 'standard', 'deep']
THRESHOLDS = [0.6, 0.7, 0.8, 0.9]


def load(run: Path) -> list[dict]:
    prs = {p['number']: p for p in json.loads((HERE / 'prs.json').read_text())['prs']}
    rows = []
    for f in sorted(run.glob('*.response.json')):
        n = int(f.name.split('.')[0])
        attempts = json.loads(f.read_text())['attempts']
        final = attempts[-1]
        gt = prs[n]['ground_truth']
        row = {'number': n, 'title': prs[n]['title'], 'gt': gt['depth'], 'lines': gt['lines'],
               'files': gt['changed_files'], 'classes': gt['path_classes'],
               'human_review_rounds': gt['human_review_rounds'],
               'review_comments': gt['review_comments'],
               'latency_s': sum(a['latency_s'] for a in attempts), 'attempts': len(attempts),
               'ok': final['ok']}
        if final['ok']:
            b = final['body']
            a = b['answers']
            sp = {LEVELS[int(k)]: v for k, v in a['size']['probabilities'].items()}
            row.update(
                size_argmax=max(sp, key=sp.get), size_probs=sp, size_score=a['size']['score'],
                size_conf=a['size']['confidence'],
                needs_design=a['needs_design']['choice'],
                needs_design_conf=a['needs_design']['confidence'],
                risky_surface=a['risky_surface']['choice'],
                risky_surface_conf=a['risky_surface']['confidence'],
                well_specified=a['well_specified']['choice'],
                in_tokens=b['usage']['input_tokens'], out_tokens=b['usage']['output_tokens'],
                model=b['model'])
        rows.append(row)
    return rows


def compact_route(r: dict, t: float, variant: str = 'primary') -> bool:
    if not r['ok']:
        return False
    if variant == 'p_compact':
        size_ok = r['size_probs']['compact'] >= t
    else:
        size_ok = r['size_argmax'] == 'compact' and r['size_conf'] >= t
    ok = size_ok and r['risky_surface'] == 'none' and r['needs_design'] == 'no'
    if variant == 'with_spec':
        ok = ok and r['well_specified'] == 'clear_acceptance_criteria'
    return ok


def metrics(rows: list[dict], variant: str) -> list[dict]:
    answered = [r for r in rows if r['ok']]
    gt_compact = [r for r in rows if r['gt'] == 'compact']
    out = []
    for t in THRESHOLDS:
        routed = [r for r in rows if compact_route(r, t, variant)]
        under = [r for r in routed if r['gt'] != 'compact']
        over = [r for r in gt_compact if not compact_route(r, t, variant)]
        out.append({
            'threshold': t, 'n': len(rows), 'answered': len(answered),
            'routed_compact': len(routed),
            'coverage': round(len(routed) / len(rows), 3) if rows else None,
            'under_triage': len(under),
            'under_triage_deep': sum(r['gt'] == 'deep' for r in under),
            'under_triage_rate_of_routed': round(len(under) / len(routed), 3) if routed else None,
            'over_triage': len(over), 'gt_compact': len(gt_compact),
            'over_triage_rate_of_gt_compact': round(len(over) / len(gt_compact), 3) if gt_compact else None,
            'compact_recall': round((len(gt_compact) - len(over)) / len(gt_compact), 3) if gt_compact else None,
            'compact_precision': round((len(routed) - len(under)) / len(routed), 3) if routed else None,
            'under_triage_cases': [{k: r[k] for k in ('number', 'title', 'gt', 'lines', 'files',
                                   'classes', 'size_probs', 'size_conf', 'risky_surface',
                                   'needs_design')} for r in under],
            'routed_compact_prs': [r['number'] for r in routed],
            'over_triage_prs': [r['number'] for r in over],
        })
    return out


def confusion(rows: list[dict]) -> dict:
    m = {g: {p: 0 for p in LEVELS + ['no_answer']} for g in LEVELS}
    for r in rows:
        m[r['gt']][r.get('size_argmax', 'no_answer')] += 1
    return m


def summary(rows: list[dict]) -> dict:
    ok = [r for r in rows if r['ok']]
    lat = [r['latency_s'] for r in rows]
    dist = lambda k: {v: sum(r.get(k) == v for r in ok) for v in sorted({r.get(k) for r in ok})}
    return {
        'n': len(rows), 'answered': len(ok), 'failed_calls': len(rows) - len(ok),
        'retries': sum(r['attempts'] - 1 for r in rows),
        'gt_distribution': {g: sum(r['gt'] == g for r in rows) for g in LEVELS},
        'confusion_gt_rows_by_jev_size_argmax': confusion(rows),
        'size_argmax_accuracy': round(sum(r.get('size_argmax') == r['gt'] for r in rows) / len(rows), 3) if rows else None,
        'answer_distributions': {k: dist(k) for k in ('needs_design', 'risky_surface', 'well_specified')},
        'tokens': {'input': sum(r.get('in_tokens', 0) for r in ok),
                   'output': sum(r.get('out_tokens', 0) for r in ok)},
        'latency_s': {'total': round(sum(lat), 2), 'median': round(statistics.median(lat), 3) if lat else None,
                      'max': round(max(lat), 3) if lat else None},
        'models': sorted({r['model'] for r in ok}),
        'routing': {v: metrics(rows, v) for v in ('primary', 'with_spec', 'p_compact')},
    }


def guard_saves(rows: list[dict], t: float = 0.6) -> list[dict]:
    """Non-compact PRs that failed exactly one guard of the primary rule at threshold t."""
    out = []
    for r in rows:
        if not r['ok'] or r['gt'] == 'compact':
            continue
        failed = [name for name, ok in (
            ('size_argmax', r['size_argmax'] == 'compact'),
            ('size_confidence', r['size_argmax'] != 'compact' or r['size_conf'] >= t),
            ('risky_surface', r['risky_surface'] == 'none'),
            ('needs_design', r['needs_design'] == 'no')) if not ok]
        if r['size_argmax'] == 'compact' and len(failed) == 1:
            out.append({'number': r['number'], 'title': r['title'], 'gt': r['gt'],
                        'lines': r['lines'], 'files': r['files'], 'only_guard_that_held': failed[0],
                        'size_probs': r['size_probs'], 'size_conf': r['size_conf'],
                        'risky_surface': r['risky_surface'], 'needs_design': r['needs_design']})
    return out


def write_results() -> None:
    runs = {'pilot-2 (questions v2)': 'calls/pilot-2', 'pilot-3 (questions v3 = frozen)': 'calls/pilot-3',
            'eval (frozen, PR+issue request)': 'calls/eval',
            'eval-issue-only (frozen, secondary arm B)': 'calls/eval-issue-only'}
    res = {'protocol': 'PROTOCOL.md', 'questions_frozen': 'questions.frozen.json', 'runs': {}}
    for name, d in runs.items():
        rows = load(HERE / d)
        s = summary(rows)
        s['dir'] = d
        s['near_misses_single_guard_t0.6'] = guard_saves(rows)
        s['per_pr'] = rows
        res['runs'][name] = s
    (HERE / 'results.json').write_text(json.dumps(res, indent=2) + '\n')


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('run', type=Path, nargs='?')
    ap.add_argument('--write-results', action='store_true')
    ap.add_argument('--rows', action='store_true', help='print per-PR rows')
    args = ap.parse_args()
    if args.write_results:
        write_results()
        return
    rows = load(HERE / args.run)
    s = summary(rows)
    if args.rows:
        for r in rows:
            if r['ok']:
                p = r['size_probs']
                print(f"{r['number']} gt={r['gt']:8} L={r['lines']:<6} F={r['files']:<4} "
                      f"size={r['size_argmax']:8} c={r['size_conf']:.2f} "
                      f"p=({p['compact']:.2f},{p['standard']:.2f},{p['deep']:.2f}) "
                      f"design={r['needs_design']:11} risk={r['risky_surface']:24} spec={r['well_specified']}")
            else:
                print(r['number'], 'NO ANSWER')
    print(json.dumps({k: v for k, v in s.items() if k != 'routing'}, indent=1))
    for v, ms in s['routing'].items():
        for m in ms:
            print(v, m['threshold'], 'routed', m['routed_compact'], 'cov', m['coverage'],
                  'under', m['under_triage'], '(deep', m['under_triage_deep'], ') over',
                  m['over_triage'], '/', m['gt_compact'], [c['number'] for c in m['under_triage_cases']])


if __name__ == '__main__':
    main()
