#!/usr/bin/env python3
"""Summarize retained paired classification runs; never extrapolate to full builds."""
import argparse
import json
from pathlib import Path
import statistics

FIELDS = ('inputTokens', 'outputTokens', 'cacheReadInputTokens', 'cacheCreationInputTokens')


def summarize(root):
    manifest = json.loads((root / 'manifest.json').read_text())
    schedule = json.loads((root / 'schedule.json').read_text())
    rows = []
    for i, entry in enumerate(schedule, 1):
        directory = root / f'run-{i:03d}-{entry["case"]}-{entry["arm"]}'
        row = json.loads((directory / 'result.json').read_text())
        assert row['case_id'] == entry['case'] and row['arm'] == entry['arm']
        rows.append({**row, 'repetition': entry['repetition'], 'directory': str(directory)})
    arms = {}
    for arm in ('baseline', 'jev'):
        group = [r for r in rows if r['arm'] == arm]
        measured = [r['llm_usage']['totals'] for r in group if r['llm_usage'] is not None]
        jev_usage = [r['jev_usage'] for r in group if r.get('jev_usage') is not None]
        raw_matches = 0
        if arm == 'jev':
            for r in group:
                response = Path(r['directory']) / 'response.json'
                if response.exists():
                    a = json.loads(response.read_text()).get('answers', {}).get('evidence_0', {})
                    raw_matches += a.get('choice') == r['expected']
        arms[arm] = {
            'attempts': len(group), 'unique_cases': len({r['case_id'] for r in group}),
            'completed': sum(r['status'] == 'completed' for r in group),
            'correct': sum(r.get('correct', False) for r in group),
            'false_support': sum(r.get('false_support', False) for r in group),
            'fallbacks': sum(r.get('fallback', False) for r in group),
            'raw_jev_correct': raw_matches if arm == 'jev' else None,
            'llm_usage_unknown': len(group) - len(measured),
            'known_llm_tokens': {f: sum(u[f] for u in measured) for f in FIELDS},
            'known_llm_total_tokens': sum(u['totalTokens'] for u in measured),
            'jev_usage_unknown': len(group) - len(jev_usage) if arm == 'jev' else 0,
            'known_jev_tokens': {f: sum(u[f] for u in jev_usage) for f in ('input_tokens', 'output_tokens')},
            'elapsed_seconds': sum(r['elapsed_seconds'] for r in group),
            'mean_elapsed_seconds': statistics.mean(r['elapsed_seconds'] for r in group),
        }
    pairs = []
    for repetition, case in sorted({(r['repetition'], r['case_id']) for r in rows}):
        pair = {r['arm']: r for r in rows if r['repetition'] == repetition and r['case_id'] == case}
        assert set(pair) == {'baseline', 'jev'}
        pairs.append({'case': case, 'repetition': repetition,
                      'both_completed': all(r['status'] == 'completed' for r in pair.values()),
                      'baseline_correct': pair['baseline'].get('correct'),
                      'jev_correct': pair['jev'].get('correct'),
                      'seconds_saved': pair['baseline']['elapsed_seconds'] - pair['jev']['elapsed_seconds']})
    b, j = arms['baseline'], arms['jev']
    known = not (b['llm_usage_unknown'] or j['llm_usage_unknown'])
    return {'scope': 'evidence classification including fixture/proof setup, not full build',
            'cohort': root.name, 'split': manifest['split'], 'arms': arms, 'pairs': pairs,
            'llm_token_reduction_fraction': 1-j['known_llm_total_tokens']/b['known_llm_total_tokens'] if known and b['known_llm_total_tokens'] else None,
            'elapsed_reduction_fraction': 1-j['elapsed_seconds']/b['elapsed_seconds'],
            'total_elapsed_ratio_baseline_to_jev': b['elapsed_seconds']/j['elapsed_seconds'],
            'comparison_valid': all(p['both_completed'] for p in pairs) and known and not j['jev_usage_unknown'],
            'configuration': {k: manifest[k] for k in ('question_version', 'model', 'jev_model', 'threshold', 'helper_sha256', 'harness_sha256', 'suite_sha256', 'versions')}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cohorts', type=Path, nargs='+')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    reports = [summarize(path) for path in args.cohorts]
    assert all(r['configuration'] == reports[0]['configuration'] for r in reports), 'Cohort configuration changed'
    with args.out.open('x') as f:
        json.dump(reports, f, indent=2, allow_nan=False)
        f.write('\n')
    for r in reports:
        print(json.dumps({k: r[k] for k in ('cohort', 'arms', 'llm_token_reduction_fraction', 'elapsed_reduction_fraction', 'comparison_valid')}))
