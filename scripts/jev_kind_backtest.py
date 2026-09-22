#!/usr/bin/env python3
"""Backtest Jev kind against frozen reference labels; does not run LLM fallback."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'gascity-jev/assets/scripts'))
import jev_kind as kind


def summarize(rows: list[dict]) -> dict:
    answered = [r for r in rows if r['status'] == 'completed']
    routed = [r for r in answered if r['decision']['route'] == 'use_kind']
    matches = lambda group: sum(r['decision']['choice'] == r['reference'] for r in group)
    ratio = lambda n, d: n / d if d else None
    confusion = {k: dict.fromkeys([*kind.CHOICES, 'failed'], 0) for k in kind.LABELS}
    for row in rows:
        predicted = row['decision']['choice'] if row['status'] == 'completed' else 'failed'
        confusion[row['reference']][predicted] += 1
    return {'cases': len(rows), 'answered': len(answered), 'routed': len(routed),
            'failures': len(rows) - len(answered), 'fallbacks': len(rows) - len(routed),
            'coverage': ratio(len(routed), len(rows)),
            'agreement_on_answered': ratio(matches(answered), len(answered)),
            'agreement_on_routed': ratio(matches(routed), len(routed)),
            'matching_routed_fraction_of_all': ratio(matches(routed), len(rows)),
            'confusion': confusion}


def validate_suite(suite: dict) -> None:
    if not isinstance(suite, dict) or suite.get('schema') != 'gc.kind-backtest.v1':
        raise ValueError('expected gc.kind-backtest.v1')
    for name in ('reference_model', 'reference_effort', 'reference_provenance', 'split'):
        if not isinstance(suite.get(name), str) or not suite[name].strip():
            raise ValueError(f'missing {name}')
    if suite['split'] not in ('pilot', 'heldout'):
        raise ValueError('split must be pilot or heldout')
    cases = suite.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('suite needs cases')
    seen = set()
    for case in cases:
        key = case.get('id')
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError('case ids must be unique nonempty strings')
        seen.add(key)
        if case.get('reference') not in kind.LABELS:
            raise ValueError('reference must be a logical kind: bug, feature, docs, chore')
        kind.materialize(case.get('snapshot'))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--model', default='jev-1.13.0')
    parser.add_argument('--threshold', type=float, default=.85)
    parser.add_argument('--labels', type=Path)
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args(argv)
    data = args.suite.read_bytes()
    suite = json.loads(data)
    validate_suite(suite)
    if not kind.transport.unit(args.threshold):
        raise ValueError('threshold must be between zero and one')
    labels = json.loads(args.labels.read_text()) if args.labels else kind.LABELS
    kind.validate_labels(labels)
    args.out.mkdir(parents=True, exist_ok=False)
    (args.out / 'suite.json').write_bytes(data)
    kind.transport.save(args.out / 'labels.json', labels)
    sources = {}
    for source in (Path(__file__), Path(kind.__file__), Path(kind.transport.__file__)):
        content = source.read_bytes()
        (args.out / source.name).write_bytes(content)
        sources[source.name] = kind.transport.digest(content)
    kind.transport.save(args.out / 'manifest.json', {
        'started_at': datetime.now(timezone.utc).isoformat(),
        'suite_sha256': kind.transport.digest(data), 'sources': sources,
        'question_version': kind.QUESTION_VERSION, 'model': args.model,
        'threshold': args.threshold, 'labels': labels, 'validate_only': args.validate_only,
        'reference_model': suite['reference_model'], 'reference_effort': suite['reference_effort'],
        'reference_provenance': suite['reference_provenance'], 'split': suite['split'],
        'scope': 'kind classifier only; historical reference; no live baseline or fallback'})
    rows = []
    started = time.monotonic()
    for index, case in enumerate(suite['cases']):
        snapshot = args.out / f'input-{index + 1:04d}.json'
        # Reference labels never enter the helper's input, including extra snapshot fields.
        kind.transport.save(snapshot, kind.materialize(case['snapshot']))
        directory = args.out / f'case-{index + 1:04d}'
        command = [str(snapshot), '--output-dir', str(directory), '--model', args.model,
                   '--threshold', str(args.threshold), '--labels', str(args.out / 'labels.json')]
        if args.validate_only:
            command.append('--validate-only')
        kind.main(command)
        report = json.loads((directory / 'report.json').read_text())
        rows.append({'id': case['id'], 'reference': case['reference'], **report})
    kind.transport.save(args.out / 'rows.json', rows)
    if args.validate_only:
        result = {'status': 'validated_only', 'cases': len(rows), 'agreement': None}
    else:
        result = {'status': 'completed', **summarize(rows)}
    measured = [r['usage'] for r in rows if isinstance(r.get('usage'), dict) and
                all(type(r['usage'].get(k)) is int and r['usage'][k] >= 0
                    for k in ('input_tokens', 'output_tokens'))]
    result.update(elapsed_seconds=time.monotonic() - started,
                  measured_usage_cases=len(measured),
                  observed_tokens={k: sum(u[k] for u in measured)
                                   for k in ('input_tokens', 'output_tokens')} if measured else None,
                  total_tokens_known=len(measured) == len(rows),
                  live_baseline_measured=False, llm_fallback_measured=False)
    if any(r['status'] == 'failed' for r in rows):
        result['status'] = 'incomplete'
    kind.transport.save(args.out / 'summary.json', result)
    print(json.dumps(result))
    return 1 if result['status'] == 'incomplete' else 0


if __name__ == '__main__':
    raise SystemExit(main())
