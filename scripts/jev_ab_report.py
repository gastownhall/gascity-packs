#!/usr/bin/env python3
"""Per-stage Claude usage and outcome report for a jev_build_ab.py experiment.

Transcript usage records carry no timestamps or bead ids, so each worker
session is attributed to the first workflow bead its prompts mention, and that
bead's gc.step_ref names the stage. Sessions that mention no workflow bead (the
bd.dog pool helpers) are reported as `helpers`.

    python3 scripts/jev_ab_report.py specs/experiments/jev-overlay-ab/ab-001
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

TOKEN_KEYS = ('input_tokens', 'cache_creation_input_tokens', 'cache_read_input_tokens', 'output_tokens')
STAGES = ('prepare', 'requirements', 'plan', 'plan-review', 'decompose', 'implement', 'summarize', 'review',
          'publish', 'helpers', 'other')


def stage_of(step_ref: str) -> str:
    ref = re.sub(r'^(jev-review-tail\.)?(jev-build(-direct|-compact)?|build-basic)\.', '', step_ref or '')
    ref = re.sub(r'\.iter(ation)?\b.*$', '', ref)
    for prefix, stage in (('prepare', 'prepare'), ('requirements', 'requirements'), ('plan-review', 'plan-review'),
                          ('plan', 'plan'), ('decompose', 'decompose'), ('do-work', 'implement'),
                          ('implement', 'implement'), ('summarize', 'summarize'), ('review', 'review'),
                          ('finalize', 'review'), ('publish', 'publish')):
        if ref.startswith(prefix):
            return stage
    return 'other'


def load_beads(run: Path) -> list[dict]:
    data = json.loads((run/'final-beads.json').read_text())
    return data if isinstance(data, list) else data.get('beads', [])


def session_stage(transcript: Path, step_refs: dict[str, str], pattern: re.Pattern) -> str:
    """Stage of the first workflow bead a session's user turns mention."""
    for line in transcript.read_text(errors='replace').splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get('type') != 'user':
            continue
        for bead in pattern.findall(json.dumps(row.get('message', {}).get('content'))):
            if step_refs.get(bead):
                return stage_of(step_refs[bead])
    return 'helpers'


def run_stages(run: Path) -> dict[str, dict]:
    """{stage: {requests, sessions, <token keys>}} with repeated chunks deduplicated by message id."""
    beads = load_beads(run)
    step_refs = {b['id']: (b.get('metadata') or {}).get('gc.step_ref', '') for b in beads}
    prefixes = sorted({b['id'].split('-')[0] for b in beads})
    pattern = re.compile(r'\b(?:%s)-[a-z0-9]{3,}\b' % '|'.join(map(re.escape, prefixes))) if prefixes else re.compile(r'$^')
    stages: dict[str, dict] = defaultdict(lambda: {'requests': 0, 'sessions': 0, **dict.fromkeys(TOKEN_KEYS, 0)})
    path = run/'transcript-usage-records.json'
    for source in json.loads(path.read_text()) if path.is_file() else []:
        transcript = Path(source['source'])
        stage = session_stage(transcript, step_refs, pattern) if transcript.is_file() else 'other'
        messages: dict[str, dict] = {}
        for record in source['records']:
            usage = messages.setdefault(record['message_id'], dict.fromkeys(TOKEN_KEYS, 0))
            for key in TOKEN_KEYS:
                usage[key] = max(usage[key], int(record['usage'].get(key) or 0))
        row = stages[stage]
        row['sessions'] += 1
        row['requests'] += len(messages)
        for usage in messages.values():
            for key in TOKEN_KEYS:
                row[key] += usage[key]
    return dict(stages)


def quality(result: dict) -> dict:
    """The harness's verdict on the result it selected; other candidates are diagnostics only."""
    return {'build_completed': result.get('fixture_tests_pass') is True,
            'hidden_pass': result.get('hidden_tests_pass') is True}


def gate(result: dict) -> str:
    """How the Jev review gate decided: `jev` when Jev answered, else its escalation."""
    rows = result.get('jev_gate_delivery') or []
    if not rows:
        return '-'
    return ', '.join(sorted({(r.get('item') or {}).get('gate') or '?' for r in rows}))


def decisions(run: Path) -> dict:
    """{type: counts} from the run's Jev decision logs: bands, labeled outcomes, Jev right/wrong, misses."""
    counts: dict[str, Counter] = defaultdict(Counter)
    for path in sorted(run.glob('decisions-*.jsonl')):
        for line in path.read_text().splitlines():
            row = json.loads(line) if line.strip() else {}
            kind = row.get('type')
            if not kind:
                continue
            if row.get('record') == 'decision':
                counts[kind][row.get('band') or 'none'] += 1
            elif row.get('record') == 'outcome':
                counts[kind]['labeled'] += 1
                counts[kind]['jev_right' if row.get('jev_correct') is True else
                             'jev_wrong' if row.get('jev_correct') is False else 'unscored'] += 1
                counts[kind]['miss'] += bool(row.get('miss'))
    return {kind: dict(c) for kind, c in counts.items()}


def collect(experiment: Path) -> list[dict]:
    runs = []
    for run in sorted(p for p in experiment.glob('run-*') if (p/'result.json').is_file()):
        result = json.loads((run/'result.json').read_text())
        stages = run_stages(run)
        runs.append({'run': run.name, 'arm': result.get('arm'), 'workload': result.get('workload'),
                     'kind': result.get('workload_kind') or '-',
                     'status': result.get('status'), 'formula': result.get('formula'),
                     'elapsed_seconds': result.get('elapsed_seconds'), **quality(result), 'gate': gate(result),
                     'skipped_lanes': sorted({lane for d in result.get('jev_gate_delivery') or []
                                              for lane in (d.get('summary') or {}).get('skipped_lanes', [])}),
                     'stages': stages, 'decisions': decisions(run),
                     'total': {k: sum(s[k] for s in stages.values()) for k in ('requests', *TOKEN_KEYS)}})
    return runs


def mean(values):
    values = [v for v in values if v is not None]
    return statistics.mean(values) if values else None


def fmt(value, digits=0):
    if value is None:
        return '-'
    return f'{value:,.{digits}f}'


def render(runs: list[dict]) -> str:
    lines = ['# Jev build A/B report', '', '## Runs', '',
             '| Run | Arm | Workload | Build | Harness status | Review gate | Hidden pass | Minutes | Requests | Output tokens | Skipped lanes |',
             '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |']
    for r in runs:
        lines.append(f"| {r['run']} | {r['arm']} | {r['workload']} | {'completed' if r['build_completed'] else 'incomplete'} | "
                     f"{r['status']} | {r['gate']} | "
                     f"{'yes' if r['hidden_pass'] else 'no'} | {fmt((r['elapsed_seconds'] or 0) / 60, 1)} | "
                     f"{r['total']['requests']} | {fmt(r['total']['output_tokens'])} | {', '.join(r['skipped_lanes']) or '-'} |")
    groups = defaultdict(list)
    for r in runs:
        groups[(r['workload'], r['arm'])].append(r)
    lines += ['', '## Means by workload and arm', '',
              '| Workload | Arm | Runs | Hidden pass | Minutes | Requests | Input+cache tokens | Output tokens |',
              '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for (workload, arm), rows in sorted(groups.items()):
        inputs = [sum(r['total'][k] for k in TOKEN_KEYS[:3]) for r in rows]
        lines.append(f"| {workload} | {arm} | {len(rows)} | {sum(r['hidden_pass'] for r in rows)}/{len(rows)} | "
                     f"{fmt(mean([(r['elapsed_seconds'] or 0) / 60 for r in rows]), 1)} | "
                     f"{fmt(mean([r['total']['requests'] for r in rows]), 1)} | {fmt(mean(inputs))} | "
                     f"{fmt(mean([r['total']['output_tokens'] for r in rows]))} |")
    arms = sorted({r['arm'] for r in runs})
    for kind in sorted({r['kind'] for r in runs}):
        lines += ['', f'## Mean requests and output tokens per stage, {kind} workloads', '',
                  '| Stage | ' + ' | '.join(f'{a} requests | {a} output' for a in arms) + ' |',
                  '| --- |' + ' --- | --- |' * len(arms)]
        for stage in (*STAGES, 'total'):
            cells = []
            for arm in arms:
                rows = [r for r in runs if r['arm'] == arm and r['kind'] == kind]
                pick = (lambda r, k: r['total'][k]) if stage == 'total' else (lambda r, k: r['stages'].get(stage, {}).get(k, 0))
                cells += [fmt(mean([pick(r, 'requests') for r in rows]), 1),
                          fmt(mean([pick(r, 'output_tokens') for r in rows]))]
            if any(c not in ('0.0', '0', '-') for c in cells):
                lines.append(f'| {stage} | ' + ' | '.join(cells) + ' |')
    kinds = sorted({k for r in runs for k in r.get('decisions', {})})
    if kinds:
        lines += ['', '## Jev decisions, all runs', '',
                  'Act means Jev decided alone; confirm and escalate left the call to Claude or the full path. '
                  'Right and wrong count labeled act decisions checked against a lane verdict or the finished diff.', '',
                  '| Decision | Act | Confirm | Escalate | Labeled | Jev right | Jev wrong | Misses |',
                  '| --- | --- | --- | --- | --- | --- | --- | --- |']
        for kind in kinds:
            c = Counter()
            for r in runs:
                c.update(r.get('decisions', {}).get(kind, {}))
            lines.append(f"| {kind} | {c['act']} | {c['confirm']} | {c['escalate']} | {c['labeled']} | "
                         f"{c['jev_right']} | {c['jev_wrong']} | {c['miss']} |")
    return '\n'.join(lines) + '\n'


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('experiment', type=Path, nargs='+', help='One or more experiment directories (e.g. a run and its reruns).')
    parser.add_argument('--json', type=Path, help='Also write the per-run data as JSON.')
    args = parser.parse_args(argv)
    runs = [run if len(args.experiment) == 1 else {**run, 'run': f"{experiment.name}/{run['run']}"}
            for experiment in args.experiment for run in collect(experiment)]
    if args.json:
        args.json.write_text(json.dumps(runs, indent=2) + '\n')
    print(render(runs), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
