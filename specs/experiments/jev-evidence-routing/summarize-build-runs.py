#!/usr/bin/env python3
"""Write a new CSV snapshot of retained build results; never infer A/B benefit."""
import argparse
import csv
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parent
rows = []
for path in sorted(root.glob('build-baseline-*/run-*/result.json')):
    result = json.loads(path.read_text())
    usage = result.get('otel_usage', {})
    totals = usage.get('totals')
    if totals is not None:
        components = [totals[k] for k in ('input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_creation_tokens')]
        assert all(type(v) is int and v >= 0 for v in components), path
        assert sum(components) == totals['total_tokens'], path
    independent_path = path.parent / 'independent-quality.json'
    independent = json.loads(independent_path.read_text()) if independent_path.exists() else {}
    rows.append({
        'cohort': path.parts[-3], 'run': path.parts[-2],
        'status': result['status'], 'arm': result['arm'],
        'elapsed_seconds': result.get('elapsed_seconds', ''),
        'elapsed_at_interrupt_ps': result.get('elapsed_at_interrupt_ps', ''),
        'request_count': usage.get('request_count', ''),
        'observed_processed_tokens': totals['total_tokens'] if totals else '',
        'telemetry_coverage': usage.get('coverage', usage.get('status', 'unknown')),
        'report_reconstructed': result.get('report_reconstructed_from_retained_artifacts', False),
        'fixture_tests_pass': result.get('fixture_tests_pass', 'unmeasured'),
        'hidden_tests_pass': result.get('hidden_tests_pass', 'unmeasured'),
        'independent_pytest_exit': independent.get('pytest_exit', ''),
        'original_tests_unchanged': independent.get('original_tests_unchanged', 'unmeasured'),
        'paired_jev_comparison_available': False,
        'result_path': str(path.relative_to(root)),
    })
if not rows:
    raise SystemExit('No retained terminal results found')
with args.output.open('x', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
print(f'Wrote {len(rows)} terminal records to {args.output}. Blank metrics are unknown, not zero.')
