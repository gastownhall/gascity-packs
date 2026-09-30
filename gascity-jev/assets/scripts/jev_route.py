#!/usr/bin/env python3
"""Intake router for jev-build: pick how many planning stages a task needs.

Reads the task bead, asks Jev the intake questions frozen by the intake-v4
study (assets/jev-intake-questions.json) about the request text, and picks one
of three formulas:

- `jev-build-compact` (no requirements, plan, plan review, decomposition or
  summary) when P(size = compact) >= the band (0.8), the spans-modules and
  hidden-scope nouls are <= 0.3, the risky surface is `none` and no design step
  is needed;
- `jev-build-direct` (no plan or plan review) when P(no design needed) >= the
  band (0.9), P(size = deep) <= 0.1, the spans-modules noul is <= 0.5 and the
  risky surface is not security or persistence;
- `jev-build` otherwise, and on every Jev failure or tripped breaker.

Audited compact and direct decisions take the full path so misses can be
measured. The decision is logged to the gate state ledger and passed to the
build as `jev_intake_decision`; the build's review-report step labels it from
the finished diff (compact: at most 3 files and 80 changed lines, no risky
path; direct: not deep).

Usage:
  jev_route.py <bead-id> [--dry-run] [--var key=value ...] [--target gc.run-operator]
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import random
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jev_client  # noqa: E402
from jev_client import JevUnavailable  # noqa: E402
from jev_decisions import StateDir, audit_rate, decision  # noqa: E402
from jev_gate import Gc, extract_json  # noqa: E402

QUESTIONS = Path(__file__).resolve().parents[1] / 'jev-intake-questions.json'
SIZE_LEVELS = ('compact', 'standard', 'deep')
MAX_REQUEST = 6000


def request_text(bead: dict) -> str:
    return (f"{bead.get('title', '')}\n\n{bead.get('description', '')}").strip()[:MAX_REQUEST]


TIERS = {'intake.compact': 'jev-build-compact', 'intake.direct': 'jev-build-direct'}


def classify(answers: dict) -> dict:
    size = answers['size']
    probabilities = {SIZE_LEVELS[int(k)]: v for k, v in size['probabilities'].items()}
    return {'size': max(probabilities, key=probabilities.get), 'size_probabilities': probabilities,
            'size_confidence': size['confidence'], 'p_compact': probabilities['compact'],
            'p_deep': probabilities['deep'], 'spans_modules': answers['spans_modules']['noul'],
            'hidden_scope': answers['hidden_scope']['noul'],
            'risky_surface': answers['risky_surface']['choice'],
            'needs_design': answers['needs_design']['choice'],
            'p_no_design': answers['needs_design']['probabilities'].get('no', 0.0),
            'well_specified': answers['well_specified']['choice']}


def tier(facts: dict, bands: dict) -> str | None:
    """The decision type whose act band these facts fall in, or None for the full path."""
    compact, direct = bands['intake.compact'], bands['intake.direct']
    if (not compact.get('tripped') and facts['p_compact'] >= compact['min_p_compact']
            and facts['spans_modules'] <= compact['max_guard'] and facts['hidden_scope'] <= compact['max_guard']
            and facts['risky_surface'] == 'none' and facts['needs_design'] == 'no'):
        return 'intake.compact'
    if (not direct.get('tripped') and facts['p_no_design'] >= direct['min_p_no_design']
            and facts['p_deep'] <= direct['max_p_deep'] and facts['spans_modules'] <= direct['max_spans_modules']
            and facts['risky_surface'] not in ('security_or_auth', 'persistence_or_migration')):
        return 'intake.direct'
    return None


def route(answers: dict | None, bands: dict, accepted: dict, rng: random.Random,
          audit_override: float | None = None) -> tuple[str, str, bool, dict]:
    """Return (formula, decision type, audited, classification). Pure; tested with recorded answers."""
    if answers is None:
        return 'jev-build', 'intake.compact', False, {}
    facts = classify(answers)
    kind = tier(facts, bands)
    if kind is None:
        return 'jev-build', 'intake.compact', False, facts
    rate = audit_override if audit_override is not None else audit_rate(accepted.get(kind, 0))
    audited = rng.random() < rate
    return ('jev-build' if audited else TIERS[kind]), kind, audited, facts


def state_dir(explicit: str) -> StateDir:
    if explicit:
        return StateDir(Path(explicit))
    city = os.environ.get('GC_CITY') or os.environ.get('GC_CITY_PATH')
    if not city:
        raise SystemExit('set --state-dir or run inside a city (GC_CITY)')
    return StateDir(Path(city) / '.gc/jev-gate')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('bead')
    parser.add_argument('--target', default='gc.run-operator')
    parser.add_argument('--title', default='', help='workflow root title passed to gc sling')
    parser.add_argument('--var', action='append', default=[], help='sling variable key=value (repeatable)')
    parser.add_argument('--state-dir', default='')
    parser.add_argument('--model', default=jev_client.DEFAULT_MODEL)
    parser.add_argument('--audit-rate', type=float, default=None)
    parser.add_argument('--dry-run', action='store_true', help='decide and log, but do not sling')
    args = parser.parse_args(argv)
    variables = dict(v.split('=', 1) for v in args.var)
    state = state_dir(args.state_dir or variables.get('jev_state_dir', ''))
    gc = Gc()
    bead = gc.show(args.bead)
    text = request_text(bead)
    questions = json.loads(QUESTIONS.read_text())
    answers, error, usage, model = None, '', {}, args.model
    try:
        reply = jev_client.ask({'request': text}, questions, model=args.model)
        answers, usage, model = reply['answers'], reply['usage'], reply['model']
    except JevUnavailable as exc:
        error = exc.reason
    bands = state.bands()
    formula, kind, audited, facts = route(answers, bands, state.accepted_audits(), random.Random(), args.audit_rate)
    act = formula in TIERS.values() or audited  # an audited act decision is still act band
    tripped = [k for k in TIERS if bands[k].get('tripped')]
    record = decision(kind, workflow_root='', step_bead=args.bead, subject=args.bead,
                      band='act' if act else ('escalate' if answers is None else 'confirm'),
                      action=formula, audit=audited, question='frozen intake questions v4',
                      answer=facts or None,
                      p=facts.get('p_no_design' if kind == 'intake.direct' else 'p_compact'),
                      thresholds={k: {n: v for n, v in bands[k].items() if n != 'tripped'} for k in TIERS},
                      reason=f'jev unavailable: {error}' if error else
                      (f"breaker tripped: {', '.join(tripped)}" if tripped else ''),
                      model=model, usage=usage)
    state.append([record])
    result = {'bead': args.bead, 'formula': formula, 'audited': audited, 'decision_id': record['decision_id'],
              'facts': facts, 'error': error}
    if not args.dry_run:
        variables.setdefault('jev_state_dir', str(state.path))
        variables['jev_intake_decision'] = record['decision_id']
        cmd = ['sling', args.target, args.bead, '--on', formula, '--json',
               *(['--title', args.title] if args.title else [])]
        for key, value in variables.items():
            cmd += ['--var', f'{key}={value}']
        out = gc.run(*cmd, timeout=600)
        try:
            data = extract_json(out)
            result['workflow_id'] = data.get('workflow_id') if isinstance(data, dict) else None
        except ValueError:
            result['sling_output'] = out[-500:]
    print(json.dumps(result))
    return 0


if __name__ == '__main__':
    sys.exit(main())
